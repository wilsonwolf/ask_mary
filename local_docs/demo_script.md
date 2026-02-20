# Ask Mary — Live Demo Script

> **Success criteria**: This demo must work end-to-end for the project to be considered complete.
> Duration: ~60 seconds (+ optional 10s safety escalation)
> Title: "Mary schedules a clinical trial visit + transport in 60 seconds"

---

## Physical Setup

- **Your phone** (+1-650-507-7348) is the participant
- **Laptop** connected to projector/TV shows the dashboard
- A **Twilio phone number** is the caller ID (the "clinic line"), configured in env vars
- A **"Start Demo Call"** button on the dashboard initiates an outbound call

---

## Dashboard Layout (What the Audience Sees)

4 panels + an events feed:

### Panel 1: Call & Safety Gates
- Call status: `Idle → Dialing → Connected`
- Disclosure flag
- Consent flag
- Identity verified flag
- DNC status (should show "Not set")

### Panel 2: Eligibility
- Trial name (e.g. "Diabetes Study A")
- 2-3 question checklist with answers (filled in real-time)
- Eligibility state: `Screening → Eligible`

### Panel 3: Scheduling
- "Checking calendar availability..." spinner
- List of next 2 available visit slots
- Slot state changes: `HELD → BOOKED`

### Panel 4: Transport
- Pickup ZIP/address
- Status: `Not started → Requested → Confirmed`
- Fake ETA / ride confirmation ID

### Events Feed (scrolling, right side or bottom)
Running log showing:
- `DISCLOSURE_ACCEPTED`
- `IDENTITY_VERIFIED`
- `SCREEN_Q1_ANSWERED`
- `AVAILABILITY_QUERY_STARTED`
- `SLOT_HELD`
- `APPOINTMENT_BOOKED`
- `TRANSPORT_CONFIRMED`

This feed is the "always moving proof" that the system is doing real work.

---

## Run-of-Show Timeline

### 0-5 seconds: Kickoff

**You say (to judges/audience):**
> "I'm going to do this live. A real phone number will call me. Our AI agent, Mary, will verify identity, pre-screen eligibility, check availability, book the appointment, and schedule transportation — all while the dashboard updates in real time."

**Action:** Click **Start Demo Call**

**Dashboard changes:**
- Call status: `Idle → Dialing...`
- Events feed: `OUTBOUND_CALL_STARTED`

---

### 5-12 seconds: Incoming call + disclosure + consent

Your phone rings. Caller ID shows the Twilio number.
You answer on speaker.

**Mary (voice):**
> "Hi, I'm Mary, an automated assistant calling on behalf of OHSU Knight Clinical Research. This call may be recorded for documentation. Press 1 to continue, or press 2 to stop."

You press **1**.

**Dashboard updates (immediately):**
- Call status: `Connected`
- `disclosed_automation = true`
- `consent_to_continue = true`
- Events feed: `CALL_CONNECTED`, `DISCLOSURE_ACCEPTED`

---

### 12-22 seconds: Identity verification (DOB year + ZIP)

**Mary:**
> "Thanks. To confirm I'm speaking with the right person, please enter your birth year as four digits."

You press **1972**.

**Mary:**
> "Thank you. Now enter your ZIP code."

You press **97205**.

**Dashboard updates:**
- `verified_identity = true`
- Participant card fills in: DOB year: 1972, ZIP: 97205, timezone: America/Los_Angeles
- Events feed: `IDENTITY_YEAR_COLLECTED`, `ZIP_COLLECTED`, `IDENTITY_VERIFIED`

---

### 22-35 seconds: Pre-screen eligibility (hard excludes only)

**Mary:**
> "I have a few quick eligibility questions. Have you been diagnosed with Type 2 diabetes?"

You say: **"Yes."**

**Mary:**
> "Are you currently pregnant or nursing?"

You say: **"No."**

**Mary:**
> "Are you currently taking insulin?"

You say: **"No."**

**Dashboard updates:**
- Eligibility panel shows answers as captured via ElevenLabs server tools
- Eligibility status: `Screening → Eligible`
- Events feed: `SCREEN_Q1=yes`, `SCREEN_Q2=no`, `SCREEN_Q3=no`, `ELIGIBILITY=ELIGIBLE`

---

### 35-50 seconds: Geo gate + calendar availability + booking

**Mary:**
> "Thanks. You're within the travel radius for this study, and transportation support is available. Let me check appointment availability."

**Dashboard "wow moment":**
- Scheduling panel: "Checking availability..." spinner
- Events feed: `AVAILABILITY_QUERY_STARTED`
- After ~0.5-1s, shows two slots: "Tuesday 10:00 AM", "Wednesday 3:00 PM"

**Mary:**
> "Press 1 for Tuesday at 10 AM, press 2 for Wednesday at 3 PM."

You press **1**.

**Dashboard updates:**
- Slot status: `HELD → BOOKED`
- Appointment card appears with time, site name, confirmation status
- Events feed: `SLOT_HELD`, `APPOINTMENT_BOOKED`

---

### 50-60 seconds: Teach-back confirmation + transport booking

**Mary:**
> "Booked. Your appointment is Tuesday at 10 AM at OHSU Knight Clinical Research Center. Press 1 to confirm these details, or press 2 to reschedule."

You press **1**.

**Mary:**
> "We can arrange transportation. Press 1 to use your home ZIP as the pickup location, or press 2 to enter a different ZIP."

You press **1**.

**Mary:**
> "Great. Your ride is scheduled. You'll receive a confirmation text with details. You'll also get prep instructions 48 hours before, a confirmation request 24 hours before, and a check-in 2 hours before. Reply RESCHEDULE anytime."

**Dashboard updates (second wow moment):**
- Transport panel: `REQUESTED → CONFIRMED`, shows fake ride ID and ETA
- Events feed: `TEACHBACK_CONFIRMED`, `TRANSPORT_CONFIRMED`, `COMMS_QUEUED`
- Comms scheduled: `PREP_MSG_SCHEDULED (T-48h)`, `CONFIRM_MSG_SCHEDULED (T-24h)`, `CHECKIN_MSG_SCHEDULED (T-2h)`

**End state on dashboard:**
- Call complete
- Eligibility = eligible
- Appointment booked
- Transport confirmed
- Comms queued

---

## Optional 10-Second Safety Escalation Add-On

After booking, say to audience:
> "I'm going to say a red-flag symptom."

Speak into the phone:
> "I'm having chest pain."

**Mary:**
> "I'm not able to provide medical advice. If this is urgent, please call emergency services. I'm creating an urgent callback request from our coordinator."

**Dashboard:**
- `handoff_queue` increments
- Shows `severity=HIGH`, `due_at=NOW`
- Events feed: `SAFETY_HANDOFF_CREATED`

---

## Why This Demo Works

- Proves **real telephony** (not a chat simulation)
- Shows **safe gates** (disclosure, consent, identity verification)
- Demonstrates real operational challenge: **availability search + booking**
- Shows retention value: **transport + comms queued**
- Stays within one minute and is highly repeatable

---

## Success Criteria

The demo is successful when ALL of the following happen in a single uninterrupted run:

1. Outbound call connects via Twilio to a real phone
2. ElevenLabs voice agent delivers disclosure and captures consent
3. Identity verification completes (DOB year + ZIP via DTMF)
4. Screening questions answered and eligibility determined
5. Calendar availability queried and appointment booked
6. Transport requested and confirmed
7. Comms cadence scheduled (T-48h, T-24h, T-2h)
8. Dashboard updates in real-time for every step
9. Events feed shows a complete audit trail
10. (Optional) Safety escalation triggers handoff queue entry
