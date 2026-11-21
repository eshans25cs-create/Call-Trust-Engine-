# Real-Time Telephony Setup Guide: Inbound & Outbound Phone Calls

This guide walks you through connecting your **Gemini Live AI Call Agent** to a real phone number so anyone can dial the number from any cell phone or landline in the world and speak with the AI in real time.

---

## 1. Overview Architecture

```
[Mobile / Landline Phone]
          │ (PSTN / Cellular Voice Network)
          ▼
[Twilio / Telnyx Telephony Carrier]
          │
          │ 1. HTTP POST /voice/incoming  (Webhook)
          │ ◄- Returns TwiML with <Stream url="wss://.../media-stream" />
          │
          │ 2. Bidirectional WebSocket Audio Stream (8kHz G.711 µ-law)
          ▼
[Gemini Live Telephony Gateway (agent/telephony/gateway.py)]
          │
          │ Transcode: 8kHz µ-law ◄-► 16kHz/24kHz Linear PCM
          ▼
[Google Gemini Multimodal Live API]
(models/gemini-2.5-flash-native-audio-latest)
```

---

## 2. Quick Setup Steps (Twilio Example)

### Step 1: Start Your Local Gateway
Launch the gateway server:
```powershell
& "d:\AI voice call\.venv\Scripts\python.exe" -m agent.telephony.gateway
```
You should see:
```
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

### Step 2: Expose Your Gateway to the Internet
Open a new terminal and run `ngrok` (or Cloudflare Tunnel):
```bash
ngrok http 8000
```
Copy your forwarding URL (e.g. `https://abc123xyz.ngrok-free.app`).

Update `PUBLIC_BASE_URL` in your `.env` file:
```ini
PUBLIC_BASE_URL=https://abc123xyz.ngrok-free.app
```

### Step 3: Configure Your Twilio Phone Number
1. Go to the [Twilio Console](https://console.twilio.com/).
2. Navigate to **Phone Numbers** $\to$ **Manage** $\to$ **Active Numbers**.
3. Click on your phone number.
4. Scroll down to the **Voice Configuration** section:
   - **A CALL COMES IN:** Select **Webhook**
   - **URL:** Enter `https://<your-ngrok-domain>/voice/incoming` (HTTP POST)
   - **CALL STATUS CHANGES:** Enter `https://<your-ngrok-domain>/voice/status` (HTTP POST)
5. Click **Save Configuration**.

---

## 3. Test Inbound Calls
Pick up your mobile phone and dial your Twilio phone number:
1. You will hear: *"Hello. You are speaking with Aria, an automated AI voice assistant. This call is processed in real time."*
2. Gemini Live will immediately listen and respond in real time.
3. If you speak while the AI is talking, **barge-in will instantly cut off the AI's audio**.
4. When you hang up, the gateway prints the full structured summary of the conversation to your server console.

---

## 4. Test Outbound Calls
You can also have the AI agent call any phone number:

1. Add your Twilio credentials to `.env`:
   ```ini
   TWILIO_ACCOUNT_SID=ACXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
   TWILIO_AUTH_TOKEN=your_auth_token_here
   TWILIO_PHONE_NUMBER=+15551234567
   ```

2. Run the outbound caller:
   ```powershell
   & "d:\AI voice call\.venv\Scripts\python.exe" -m agent.telephony.outbound --to +1XXXXXXXXXX
   ```

3. Your mobile phone will ring. When you answer, you will be connected directly to the real-time Gemini Live AI agent.

---

## 5. 24/7 Cloud Deployment (Docker)

To deploy to any cloud server (AWS, Google Cloud Run, DigitalOcean, Hetzner, etc.):
```bash
docker-compose up -d
```
The gateway will run continuously in the background with auto-restart.
