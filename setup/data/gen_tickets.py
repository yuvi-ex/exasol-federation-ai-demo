#!/usr/bin/env python3
"""Synthetic B2B support tickets keyed to Snowflake SNOWFLAKE_SAMPLE_DATA.TPCH_SF1 customers.
SYNTHETIC -- say so on stage. Deterministic (seed 42).
CATEGORY and CHURN_INTENT are ground truth kept for evaluation; the search never sees them.
Phrasings deliberately avoid the category's obvious keyword so semantic search has to earn it."""
import csv, random, datetime
R = random.Random(42)
N = 5000
PRODUCTS = ["brass fittings", "polished steel brackets", "anodized copper pipe", "burnished tin sheets",
            "plated nickel bolts", "brushed aluminium panels", "economy brass valves", "standard steel flanges",
            "large copper coils", "promo tin cans", "medium plated fasteners", "small polished rods"]
CHANNELS = ["email", "portal", "phone transcript", "account manager note", "chat"]
CATS = {
 "late_delivery": [
   "Our shipment of {p} was promised for the {d} and still has not turned up.",
   "Third week waiting on the {p}. The tracking page has said 'in transit' since the {d}.",
   "We planned a production run around the {p} arriving on the {d}. Nothing has arrived and the line is idle.",
   "Can someone tell me where order for {p} is? It was meant to be here days ago.",
   "The {p} consignment slipped again. That is the second slip this quarter.",
   "Your carrier keeps rescheduling. We were told the {d}, then Friday, now 'next week' for the {p}.",
   "Still no sign of the {p}. Our warehouse team has been standing by since the {d}."],
 "damaged": [
   "Half the {p} came out of the crate bent and scratched.",
   "Pallet of {p} arrived with the wrapping torn open and several pieces dented.",
   "The {p} were crushed in transit, the box looked like it had been dropped from a height.",
   "Opened the delivery of {p} this morning and a good third of them are cracked.",
   "Received the {p} but the packaging was soaked through and the metal has started to rust.",
   "Several of the {p} were snapped in two when we unpacked them."],
 "wrong_item": [
   "We ordered {p} and received something completely different.",
   "The box is labelled {p} but inside are parts in the wrong size.",
   "This is not what we asked for. The {p} on the invoice do not match what is on the pallet.",
   "Got 200 units of the wrong finish instead of the {p} we specified.",
   "Your warehouse picked the wrong SKU again, these are not {p}."],
 "billing": [
   "We were invoiced twice for the same batch of {p}.",
   "The price on the invoice for {p} is higher than the price we agreed in the contract.",
   "Please explain the extra surcharge on our last statement for the {p}.",
   "Our finance team cannot reconcile your invoice, the quantities of {p} are off.",
   "We still have not received the credit note you promised for the {p}."],
 "quality": [
   "The latest batch of {p} does not meet the tolerance in our spec, the threads are off.",
   "Our QA rejected the {p}. Finish is uneven and some pieces fail the stress test.",
   "Compared with last year the {p} feel cheaper and wear out much faster.",
   "Two of our customers returned products built with your {p} because of early failure."],
 "praise": [
   "Just wanted to say the {p} arrived early and in perfect condition. Great job.",
   "Your account team sorted our {p} issue in a single call, really appreciated.",
   "Consistently good quality on the {p}, our QA has not flagged anything in months.",
   "Thanks for the quick turnaround on the {p}, it saved our production week."],
 "account": [
   "I cannot log into the ordering portal, the password reset email never arrives.",
   "Please add my colleague as a second contact on our account.",
   "Could you send us a copy of last year's statements for our auditors?",
   "We have moved office, please update the delivery address on our account."],
}
WEIGHTS = {"late_delivery": 26, "damaged": 16, "wrong_item": 11, "billing": 14, "quality": 11, "praise": 12, "account": 10}
CHURN = ["If this happens again we will move our business to another supplier.",
         "Frankly we are already talking to your competitors.",
         "We are reviewing whether to renew the contract at the end of the quarter.",
         "Our procurement team has asked me to find an alternative vendor.",
         "This is the last chance, after this we are going elsewhere.",
         "Honestly I am not sure we can keep working with you."]
OPEN = ["", "", "Hi team, ", "Hello, ", "Good morning. ", "To whom it may concern: ", "Hi {n}, ", "Following up: ", "Urgent: "]
NAMES = ["Priya", "Tom", "support", "Anna", "Rahul", "Marco", "Mei", "account team"]
QTY = ["", "", " ({q} units)", " (PO {po}, {q} units)", " on PO {po}"]
CLOSE = ["", "", "Please call me back today.", "Regards, procurement.", "Need an answer by end of day.",
         "Reference attached.", "Thanks.", "Escalating to my manager if not resolved."]
CHURN_P = {"late_delivery": .30, "damaged": .25, "wrong_item": .22, "billing": .28, "quality": .35, "praise": 0, "account": .03}

def custkey():
    while True:
        k = R.randint(1, 150000)
        if k % 3: return k          # TPC-H: custkey % 3 == 0 never orders
# A few "repeat complainers" make the churn story realistic: 300 customers get 30% of tickets.
HOT = [custkey() for _ in range(300)]
start = datetime.date(1997, 1, 1)
rows = []
for i in range(1, N + 1):
    cat = R.choices(list(WEIGHTS), weights=list(WEIGHTS.values()))[0]
    d = start + datetime.timedelta(days=R.randint(0, 574))
    prod = R.choice(PRODUCTS) + R.choice(QTY).format(q=R.choice([40, 75, 120, 200, 250, 500, 800, 1200]), po=R.randint(10000, 99999))
    op = R.choice(OPEN).format(n=R.choice(NAMES))
    body = R.choice(CATS[cat])
    if op.endswith(', ') and not body.startswith('I '): body = body[0].lower() + body[1:]
    text = op + body.format(p=prod, d=(d - datetime.timedelta(days=R.randint(3, 20))).strftime('%-d %B'))
    text = text[0].upper() + text[1:]
    churn = int(R.random() < CHURN_P[cat])
    if churn: text += " " + R.choice(CHURN)
    tail = R.choice(CLOSE)
    if tail: text += " " + tail
    ck = R.choice(HOT) if R.random() < .3 else custkey()
    rows.append([i, ck, d.isoformat(), R.choice(CHANNELS), cat, churn, text])
with open('support_tickets.csv', 'w', newline='') as f:
    w = csv.writer(f, lineterminator='\n')   # LF only: CRLF breaks Exasol CSV import
    w.writerow(["TICKET_ID", "C_CUSTKEY", "CREATED_DATE", "CHANNEL", "CATEGORY", "CHURN_INTENT", "TICKET_TEXT"])
    w.writerows(rows)
from collections import Counter
print(len(rows), "tickets;", Counter(r[4] for r in rows).most_common(), "; churn", sum(r[5] for r in rows),
      "; distinct customers", len({r[1] for r in rows}))
