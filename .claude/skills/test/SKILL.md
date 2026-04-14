---
name: test
description: End-to-end browser test for the Weekend Buddy Agent bot on Lark. Controls Chrome to open the bot chat, send the 5 preference questions, select an activity card, invite buddies, and confirm the plan.
---

# Weekend Buddy Agent — End-to-End Browser Test

Automates the full user flow through the Lark web client using the `mcp__Claude_in_Chrome__*` tools.

## When to Use

- After deploying a new version to verify the end-to-end flow works
- When debugging a specific step in the conversation flow
- To confirm a bug fix works in the real Lark environment

## Prerequisites

- Chrome must be open and logged into the Lark test workspace
- The Vercel backend must be running and reachable
- The Weekend Buddy Agent bot must be visible in the chat list

## Test URL

```
Sandbox: https://test-dhkystf4ktrf.sg.larksuite.com/next/messenger/
Production: https://csgfye2fddl6.sg.larksuite.com/next/messenger/
```

## Step-by-Step Procedure

### Step 1 — Get tab context and navigate

```
Use mcp__Claude_in_Chrome__tabs_context_mcp (createIfEmpty: true) to get the tab ID.
Use mcp__Claude_in_Chrome__navigate to open the Lark messenger URL.
```

### Step 2 — Open the Weekend Buddy Agent chat

The chat list renders in a Shadow DOM / React tree that is not fully accessible via the accessibility tree.
Use JavaScript to find and click the chat by text content:

```javascript
// Find the "Weekend Buddy Agent" text node and click 3 levels up
const el = [...document.querySelectorAll('*')].find(e =>
  e.childNodes.length === 1 &&
  e.childNodes[0].nodeType === 3 &&
  e.textContent.trim() === 'Weekend Buddy Agent'
);
el?.parentElement?.parentElement?.parentElement?.click();
```

Verify by calling `mcp__Claude_in_Chrome__get_page_text` and confirming the chat panel shows
`"Message Weekend Buddy Agent"` in the page text.

### Step 3 — Reset the session

Send "plan my weekend" to ensure a clean state before testing:

```javascript
const input = document.querySelector('[contenteditable="true"]');
input.focus();
input.textContent = '';
input.dispatchEvent(new InputEvent('input', { bubbles: true }));
setTimeout(() => {
  input.textContent = 'plan my weekend';
  input.dispatchEvent(new InputEvent('input', { bubbles: true }));
  setTimeout(() => {
    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', code: 'Enter', keyCode: 13, bubbles: true }));
  }, 200);
}, 200);
```

**Expected bot reply:** `"Let's start fresh!"`

### Step 4 — Helper: send a message

Reuse this pattern for every message send. Always clear the input first, then set text, then dispatch Enter:

```javascript
function sendMessage(text) {
  const input = document.querySelector('[contenteditable="true"]');
  input.focus();
  input.textContent = '';
  input.dispatchEvent(new InputEvent('input', { bubbles: true }));
  setTimeout(() => {
    input.textContent = text;
    input.dispatchEvent(new InputEvent('input', { bubbles: true }));
    setTimeout(() => {
      input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', code: 'Enter', keyCode: 13, bubbles: true }));
    }, 300);
  }, 200);
}
sendMessage('YOUR_TEXT_HERE');
```

### Step 5 — Answer the 5 preference questions

After each send, call `mcp__Claude_in_Chrome__get_page_text` to confirm the bot asked the next question before sending the next answer.

| # | Send | Expected bot question |
|---|---|---|
| 1 | `hiking` | `"What's your budget like? 💰"` |
| 2 | `low` | `"What vibe are you going for? ✨"` |
| 3 | `adventurous` | `"Any location preference? 📍"` |
| 4 | `nature` | `"When are you free? 🗓️"` |
| 5 | `Saturday morning` | Suggestions card: `"🎯 Weekend Suggestions"` |

**Note:** The first message (`hiking`) triggers Q1 from IDLE phase, so it may arrive as a bot question
before the message is fully sent. Wait for the page text to update before sending the next message.

### Step 6 — Select an activity from the suggestions card

Click the first "Pick this! 👈" button (highest-ranked match):

```javascript
const buttons = [...document.querySelectorAll('button')].filter(b => b.textContent.trim() === 'Pick this! 👈');
buttons[0]?.click();
```

**Expected result:** A new `"👥 Find Your Buddies"` card appears listing buddy candidates with `"Invite <Name> 🙋"` buttons.

### Step 7 — Invite buddies

Click each buddy's invite button. The buddy list is dynamically populated based on the selected activity.

```javascript
// Invite the first buddy
const buttons = [...document.querySelectorAll('button')];
const first = buttons.find(b => b.textContent.includes('Invite '));
first?.click();
```

Repeat for additional buddies if desired. Each tap shows a toast `"✅ <Name> added to the invite list!"`.

### Step 8 — Confirm buddy selection

Click "Done Selecting ✅" to lock the buddy list and trigger the invite preview card:

```javascript
const btn = [...document.querySelectorAll('button')].find(b => b.textContent.includes('Done Selecting'));
btn?.click();
```

**Expected result:** A `"📬 Ready to Send Invites?"` card appears showing:
- Plan summary (activity, type, budget, vibe)
- Attendees list
- LLM-generated invite message preview
- "Send Invites ✉️" and "Start Over 🔄" buttons

### Step 9 — Send the invites

Click "Send Invites ✉️" to confirm the plan:

```javascript
const btn = [...document.querySelectorAll('button')].find(b => b.textContent.includes('Send Invites'));
btn?.click();
```

**Expected result:** A `"✅ Weekend Plan Locked In!"` confirmation card appears with the full plan summary and `"Have an amazing weekend! 🥳"`.

---

## Verification Checklist

After running the full flow, confirm the following in the page text:

- [ ] `"Let's start fresh!"` appeared after "start over"
- [ ] All 5 preference questions were asked in order
- [ ] `"🎯 Weekend Suggestions"` card appeared with 3 activities
- [ ] Each suggestion includes a `"🎯 Why for you:"` personalised reason
- [ ] `"👥 Find Your Buddies"` card appeared after selecting an activity
- [ ] Buddy names match interests for the selected activity type
- [ ] `"📬 Ready to Send Invites?"` card appeared with correct attendees
- [ ] `"✅ Weekend Plan Locked In!"` confirmation card appeared

## Alternate Flows to Test

**Go Solo:** At Step 7, click "Go Solo 🚶" instead of inviting buddies. Expect the invite preview card to show no attendees.

**Start Over mid-flow:** At any step, click "Start Over 🔄" on a card. Expect the session to reset and the bot to ask for the activity again.

**Same as last time:** After completing a full flow, send "start over", then send "same as last time". Expect the bot to restore the previous preferences and skip straight to the suggestions card (if all 5 fields were saved).

**Reject invite:** At Step 9, click "Start Over 🔄" on the invite preview card instead of sending. Expect a full session reset.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Bot replies with greeting instead of extracting preference | Greeting keyword substring match (e.g. "hi" in "hiking") | Check `is_greeting()` in `orchestrator.py` — ensure whole-word regex match |
| Bot repeats the same question | Phase not set to `GATHERING` after first answer | Check `PreferenceAgent._process_response` — `phase` must be set on every preference update |
| `Tool not found: send_lark_text` error | MockLLMClient routing collision between agents | Check `mock_client.py` system context routing strings — ensure they are unique substrings |
| Suggestions card doesn't appear after Q5 | `_profile_is_complete` check failing | Verify all 5 fields are non-None in `SessionState.intent_profile` |
| "Send Invites" toast doesn't appear | Lark 3s callback timeout exceeded | Ensure only one outbound API call per card handler before returning the toast response |
