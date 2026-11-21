# Android Telephony Call Audio Architecture & Technical Reality Guide

This document provides a rigorous, senior-level analysis of live call audio access on Android devices, explaining why certain integration paths are restricted by the operating system, what actually works, and how to build production-grade real-time voice call agents.

---

## 1. The Cellular Call Audio Dilemma on Android

Many developers attempt to build an app that silently listens to standard cellular phone calls (placed over GSM, LTE, or 5G through the phone's native dialer) and speaks back into the call. 

On modern Android (Android 9 Pie through Android 15), **this is technically blocked by the Android OS security architecture for all non-system applications**.

### Why Direct Cellular Call Audio Is Blocked:

1. **`MediaRecorder.AudioSource.VOICE_CALL`, `VOICE_DOWNLINK`, and `VOICE_UPLINK`:**
   - In Android 4.0 to 8.0, apps could sometimes read `AudioSource.VOICE_CALL`.
   - Starting with Android 9 (API 28), Google enforced that accessing `VOICE_CALL` requires the permission:
     `android.permission.CAPTURE_AUDIO_OUTPUT`
   - **Protection Level:** `signature|privileged`. This permission is **never granted to standard third-party apps**. It is exclusively reserved for system apps signed by the device manufacturer (OEM) or cellular carrier installed in `/system/priv-app`.
   - Attempting to record from `VOICE_CALL` without system signature throws a `SecurityException` or returns silent zero-filled audio buffers.

2. **`AudioPlaybackCaptureConfiguration` (Android 10+):**
   - Android 10 introduced audio playback capture for screen recording and streaming.
   - However, the official Android framework explicitly restricts audio attributes:
     ```java
     // Android Framework Source Check:
     if (usage == AudioAttributes.USAGE_VOICE_COMMUNICATION || 
         usage == AudioAttributes.USAGE_VOICE_COMMUNICATION_SIGNALLING) {
         // Disallowed from capture!
     }
     ```
   - Standard phone calls and VoIP apps with `USAGE_VOICE_COMMUNICATION` are permanently excluded from capture.

3. **Accessibility Service Restrictions (Android 12/13/14+):**
   - Earlier call recorder apps exploited Accessibility APIs as a workaround to tap the microphone during calls.
   - In 2022, Google updated Google Play Store policies and Android runtime security to disallow Accessibility APIs from being used for call audio recording. Apps attempting this are banned or blocked at runtime.

4. **Hardware Audio HAL Isolation:**
   - On Qualcomm, MediaTek, and Samsung Exynos chips, the cellular modem routes voice call audio directly to the audio codec hardware (DSP) via a dedicated hardware PCM bus (I2S/SLIMbus), completely bypassing the Android Application Processor (AP) for low power and latency. The Android OS kernel itself often does not route downlink cellular audio through user-space.

---

## 2. Tested & Supported Live Call Architectures

| Architecture | Both Sides of Call Accessible? | Real Cellular Phone Numbers? | Latency | Complexity | Production Viability |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **1. Cloud Telephony Gateway (SIP / Twilio / Telnyx)** | **YES (100%)** | **YES** | ~150-350ms | Low | **Highest (Industry Standard)** |
| **2. Android VoIP `ConnectionService` (Custom App)** | **YES (100%)** | Requires SIP trunk or VoIP account | ~120-250ms | Medium | **High for proprietary apps** |
| **3. Bluetooth SCO / Hardware Companion** | **YES (via loopback)** | **YES** | ~200-400ms | High | Viable for testing / specialized hardware |
| **4. Third-Party Android Native Cellular Tap** | **NO (Blocked)** | N/A | N/A | Impossible | **Non-functional on non-rooted Android 9+** |

---

## 3. Recommended Approach: Cloud Telephony Gateway

Instead of fighting mobile OS sandboxes, the real-world standard for AI call agents (used by Google Duplex, Bland, Retell, and Vapi) is **Cloud Telephony Ingest**:
1. You purchase a virtual phone number (or forward calls from your mobile phone).
2. The carrier (Twilio, Telnyx, or an Asterisk/FreeSWITCH SIP PBX) receives the cellular call.
3. The carrier opens a real-time bidirectional WebSocket stream directly to your server (`agent/telephony/gateway.py`).
4. Both caller audio (inbound) and AI audio (outbound) are cleanly separated, full-duplex, and ultra-low latency.

---

## 4. Alternative Supported Approach: Android VoIP `ConnectionService`

If you must run a voice call on an Android device itself, you build an **Android VoIP Application**:
- The app uses `TelecomManager` and extends `ConnectionService`.
- Android integrates your call directly into the native system UI (heads-up call notification, lock screen dialer).
- Because your app is the active communication client, it legally owns:
  - `AudioRecord` (microphone at 16,000 Hz)
  - `AudioTrack` (speaker playback at 24,000 Hz)
- The app streams audio frames over WebSocket directly to the Gemini Live agent.

See [`VoipConnectionService.kt`](file:///d:/AI%20voice%20call/android/VoipConnectionService.kt) for the complete reference implementation.
