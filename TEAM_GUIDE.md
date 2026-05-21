# Quick Start Guide - For Your Team

## What This System Does

✨ **Solves Your Problem**: Instead of searching across 8 Excel files to find dealers and track citations, just:

1. **Enter a dealer ID** → Get their full history + suggestions
2. **Build the citation** (on backlink directory website)
3. **Record it** → System updates automatically

**Result**: Find dealer info in 5 seconds instead of 15 minutes! ⚡

---

## 🚀 Getting Started (For Your Office Mates)

### One-Time Setup (Admin Only)

```bash
# 1. Open PowerShell/Command Prompt
# 2. Go to project folder
cd "c:\Users\Atharv Raskar\Desktop\AI LB Prototype"

# 3. Install dependencies (one-time only)
python -m pip install -r requirements.txt

# 4. Import data from Excel files
python scripts/import_data.py

# 5. Start the application
python app.py
```

**When you see this, you're ready:**
```
Running on http://127.0.0.1:5000
```

### Daily Usage (For Team Members)

1. **Open browser**: `http://localhost:5000`
2. Choose one of 4 options:

---

## 📝 Daily Workflows

### Workflow 1: Find Dealer Info (Most Used)

**Goal**: See what citations a dealer has + what to build next

```
1. Click "Find Dealer"
2. Enter dealer ID (e.g., 20000)
3. View:
   • Dealer name & total citations
   • All citations already built with dates
   • 2 suggested citations ready to build
4. Open each suggested directory link and build the citation
```

### Workflow 2: Record a New Citation

**Goal**: Add a citation to database after you've built it

```
1. Click "Add Citation"
2. Enter dealer ID
3. See dealer details auto-load
4. Select the directory you just built
5. Click "Add Citation"
6. ✓ Done! Won't be suggested for this dealer for 6 months
```

### Workflow 3: Check Overall Status

**Goal**: See which dealers need citations this month

```
1. Click "Dashboard"
2. View:
   • Total dealers & directories
   • Total citations built so far
   • Which dealers need citations this month
   • List of all dealers with their stats
```

### Workflow 4: Home Page

**Goal**: Quick overview of everything

```
1. Click "Home"
2. See:
   • Total dealers
   • Total directories available
   • Citations built so far
   • Dealers needing citations
   • Quick start guide
```

---

## 🎯 Example: Building Citations for One Dealer

### Dealer: Brew Haven Cafe (ID: 20000)

**Step 1: Check Current Status**
```
Go to "Find Dealer"
Enter: 20000
Result shows:
  ✓ Name: Brew Haven Cafe
  ✓ Already built: 5 citations
  ✓ Last month: 1 citation
  ✓ Needs: 1 more this month

Suggested next: YouTube, GitHub, Instagram Business
```

**Step 2: Build the Citation**
- Click on suggested directory link (e.g., YouTube)
- Create/update their business profile
- Return to application

**Step 3: Record the Citation**
```
Go to "Add Citation"
Enter: 20000
Select: YouTube
Click: "Add Citation"
Result: ✓ Citation recorded
```

**Step 4: Build Second Citation**
- Repeat Steps 2-3 with another suggested directory

**Step 5: Verify Update**
```
Go back to "Find Dealer"
Enter: 20000
Now shows:
  ✓ Total citations: 7 (was 5)
  ✓ Suggestions: Different 2 directories
  ✓ Already includes YouTube in history
```

---

## ⚙️ Technical Details

### The 6-Month Rule

When you add a citation, it's locked for that dealer for 6 months:

```
Today: Add YouTube for Dealer 20000
Until: 6 months from today → YouTube won't be suggested

After 6 months: YouTube becomes available again
```

**Why?** Prevent building the same citation too quickly. Better for SEO.

### Smart Suggestions

When you request suggestions, the system:
1. ✓ Checks all 60 backlink directories
2. ✗ Removes directories used in last 6 months
3. ✗ Removes already built citations
4. ✓ Randomly picks 2 from remaining (fair distribution)

**Result**: You always get available, appropriate suggestions

---

## 🎓 Tips & Tricks

### Tip 1: Use Dashboard to Plan
- Before starting work, check "Dashboard"
- See which dealers need citations
- Plan your work accordingly

### Tip 2: Batch Process Dealers
- Search for dealer #1, build 2 citations, record them
- Search for dealer #2, build 2 citations, record them
- Continue for multiple dealers in one session

### Tip 3: Check Dealer Before Building
- Always use "Find Dealer" first
- Verify they're not already maxed out for the month
- Only build if "Needed" column shows > 0

### Tip 4: Use Quick Links
- On Dashboard, click dealer name to jump directly to their lookup
- Saves typing their ID each time

---

## 🔍 Understanding the Interface

### Colors & Badges

| Color | Meaning |
|-------|---------|
| 🟢 Green | Ready to build (not in last 6 months) |
| 🟡 Yellow | Recently built (within last 6 months) |
| 🟣 Purple | Primary action button |
| 🔵 Blue | Information messages |

### Status Indicators

| Status | Meaning | Action |
|--------|---------|--------|
| This Month: 0, Needed: 2 | Dealer needs citations | Build 2 citations |
| This Month: 1, Needed: 1 | Dealer needs 1 more | Build 1 citation |
| This Month: 2, Needed: 0 | Dealer is done | Move to next dealer |

---

## 🆘 Troubleshooting

### Problem: Can't connect to application
```
Error: "Connection refused"
Solution:
1. Make sure app.py is running
2. Check terminal shows "Running on http://127.0.0.1:5000"
3. Make sure you're at right URL: http://localhost:5000
4. Try: http://127.0.0.1:5000 instead
```

### Problem: Dealer not found
```
Error: "Dealer not found" 
Solution:
1. Check dealer ID is correct (from Excel file)
2. Check you entered it with no spaces
3. Try a known dealer: 20000, 20001, 20002, etc.
```

### Problem: No suggestions available
```
Error: "No available citations at this time"
Meaning: All 60 directories were built in last 6 months
Solution: Wait a few days, or this is unlikely in real scenario
```

### Problem: "Add Citation" button won't respond
```
Solution:
1. Make sure you selected a directory
2. Check dealer ID is valid
3. Refresh page and try again
4. Check browser console (F12) for errors
```

---

## 📊 Dashboard Explained

The dashboard shows you:

**Top Statistics (4 boxes)**
- Total Dealers: How many dealers in system
- Backlink Directories: How many directories available (should be 60)
- Total Citations Built: All time total
- Avg Citations/Dealer: Average per dealer

**Dealers Needing Citations**
Shows dealers who haven't built 2 citations this month with:
- Dealer ID & Name
- How many built this month
- How many still needed

**All Dealers Table**
Shows every dealer with:
- ID & Name (click name to find dealer)
- Total citations ever built
- How many built this month

---

## ✅ Quality Checklist Before Using

Before showing to your team, verify:

- [ ] `python app.py` runs without errors
- [ ] Database file exists: `database/backlinks.db`
- [ ] Can access: http://localhost:5000
- [ ] "Find Dealer" page loads
- [ ] Can search for dealer ID 20000
- [ ] Suggestions appear
- [ ] Can "Add Citation" and it succeeds
- [ ] Dashboard shows correct numbers

---

## 📞 Quick Help

| Question | Answer |
|----------|--------|
| Where do I enter dealer ID? | "Find Dealer" page |
| How do I record a citation? | "Add Citation" page |
| What's my next task? | Check "Dashboard" |
| Why aren't old directories suggested? | 6-month rule prevents repetition |
| Can I build same citation twice? | No, system prevents duplicates |
| How long to find dealer info? | 5 seconds vs. 15 mins in Excel |

---

## 🎉 Success!

You've successfully:
- ✅ Eliminated manual Excel searching
- ✅ Automated 6-month tracking
- ✅ Centralized all dealer data
- ✅ Reduced work time by ~90%
- ✅ Prevented citation duplicates
- ✅ Created audit trail with timestamps

**Next step**: Invite your team and watch them save hours!

---

**Last Updated**: 2026-05-20  
**Status**: Ready for Team Use  
**Version**: 1.0
