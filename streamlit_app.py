"""Hospital Appointment Scheduler - patient pages + password-protected admin page."""
import sqlite3
from datetime import date

import streamlit as st

st.set_page_config(page_title="Clinic Scheduler", page_icon="🏥", layout="centered")

DB = "scheduler.db"
SLOTS = ["09:00", "09:30", "10:00", "10:30", "11:00", "11:30",
         "14:00", "14:30", "15:00", "15:30", "16:00", "16:30"]
DEFAULT_DOCTORS = [("Dr. Asha Menon", "Cardiology"), ("Dr. Rohan Verma", "Orthopedics"),
                   ("Dr. Priya Nair", "Pediatrics"), ("Dr. Imran Qureshi", "General Medicine"),
                   ("Dr. Lena Fischer", "Dermatology")]
ICON = {"Pending": "🟡", "Approved": "🟢", "Rejected": "🔴"}


def conn():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    c.execute("""CREATE TABLE IF NOT EXISTS bookings(
        id INTEGER PRIMARY KEY, patient TEXT NOT NULL, phone TEXT NOT NULL,
        doctor TEXT NOT NULL, day TEXT NOT NULL, slot TEXT NOT NULL,
        reason TEXT, status TEXT NOT NULL DEFAULT 'Pending')""")
    c.execute("""CREATE TABLE IF NOT EXISTS doctors(
        id INTEGER PRIMARY KEY, name TEXT NOT NULL, specialty TEXT NOT NULL,
        UNIQUE(name, specialty))""")
    if not c.execute("SELECT 1 FROM doctors").fetchone():
        c.executemany("INSERT INTO doctors(name, specialty) VALUES (?,?)", DEFAULT_DOCTORS)
        c.commit()
    # a slot is blocked by Pending/Approved bookings; rejected ones free it again
    c.execute("""CREATE UNIQUE INDEX IF NOT EXISTS one_per_slot
                 ON bookings(doctor, day, slot) WHERE status != 'Rejected'""")
    return c


def get_doctors():
    with conn() as c:
        return [f"{r['name']} - {r['specialty']}" for r in
                c.execute("SELECT name, specialty FROM doctors ORDER BY name")]


# ---------------- patient: book ----------------
def book_page():
    st.title("🏥 Book an appointment")
    st.caption("Your request is sent to the hospital for approval.")
    doctors = get_doctors()
    if not doctors:
        st.warning("No doctors are available right now. Please check back later.")
        return
    doctor = st.selectbox("Doctor", doctors)
    day = st.date_input("Date", min_value=date.today()).isoformat()
    with conn() as c:
        taken = {r["slot"] for r in c.execute(
            "SELECT slot FROM bookings WHERE doctor=? AND day=? AND status!='Rejected'",
            (doctor, day))}
    free = [s for s in SLOTS if s not in taken]

    if not free:
        st.warning("No times left on this date. Try another day.")
        return
    with st.form("book"):
        slot = st.selectbox("Available times", free)
        patient = st.text_input("Patient name")
        phone = st.text_input("Phone number")
        reason = st.text_input("Reason for visit (optional)")
        sent = st.form_submit_button("Request appointment", type="primary")
    if sent:
        if not patient.strip() or not phone.strip():
            st.error("Enter the patient name and phone number.")
            return
        try:
            with conn() as c:
                cur = c.execute(
                    "INSERT INTO bookings(patient,phone,doctor,day,slot,reason) VALUES (?,?,?,?,?,?)",
                    (patient.strip(), phone.strip(), doctor, day, slot, reason.strip()))
            st.success(f"Request sent (ID {cur.lastrowid}) for {day} at {slot}. "
                       "Check the status in 'My bookings'.")
        except sqlite3.IntegrityError:
            st.error("That time was just taken. Pick another.")


# ---------------- patient: status ----------------
def status_page():
    st.title("📋 My bookings")
    phone = st.text_input("Enter the phone number you booked with")
    if not phone.strip():
        st.info("Enter your phone number to see your appointments.")
        return
    with conn() as c:
        rows = c.execute("SELECT * FROM bookings WHERE phone=? ORDER BY day, slot",
                         (phone.strip(),)).fetchall()
    if not rows:
        st.warning("No bookings found for this number.")
    for r in rows:
        with st.container(border=True):
            st.markdown(f"{ICON[r['status']]} **{r['status']}** · ID {r['id']}  \n"
                        f"{r['doctor']}  \n{r['day']} at {r['slot']}")
            if r["status"] == "Rejected":
                st.caption("This request was not approved. Please book another time.")


# ---------------- admin ----------------
def set_status(booking_id, status):
    with conn() as c:
        c.execute("UPDATE bookings SET status=? WHERE id=?", (status, booking_id))
    st.rerun()


def admin_page():
    st.title("🔒 Admin")
    if not st.session_state.get("admin"):
        pw = st.text_input("Admin password", type="password")
        if st.button("Log in", type="primary"):
            if pw == st.secrets.get("ADMIN_PASSWORD", "admin123"):
                st.session_state["admin"] = True
                st.rerun()
            else:
                st.error("Wrong password.")
        return

    if st.button("Log out"):
        st.session_state["admin"] = False
        st.rerun()

    tab_appts, tab_docs = st.tabs(["Appointments", "Doctors"])
    with tab_appts:
        admin_appointments()
    with tab_docs:
        admin_doctors()


def admin_doctors():
    st.subheader("Add a doctor")
    with st.form("add_doctor", clear_on_submit=True):
        name = st.text_input("Doctor name", placeholder="Dr. Anil Kumar")
        specialty = st.text_input("Profession / specialty", placeholder="Neurology")
        added = st.form_submit_button("Add doctor", type="primary")
    if added:
        if not name.strip() or not specialty.strip():
            st.error("Enter both the doctor's name and profession.")
        else:
            try:
                with conn() as c:
                    c.execute("INSERT INTO doctors(name, specialty) VALUES (?,?)",
                              (name.strip(), specialty.strip()))
                st.success(f"Added {name.strip()} ({specialty.strip()}). Patients can book them now.")
            except sqlite3.IntegrityError:
                st.error("This doctor is already in the list.")

    st.subheader("Current doctors")
    with conn() as c:
        docs = c.execute("SELECT * FROM doctors ORDER BY name").fetchall()
    if not docs:
        st.info("No doctors yet. Add one above.")
    for d in docs:
        with st.container(border=True):
            st.markdown(f"**{d['name']}**  \n{d['specialty']}")
            if st.button("Remove", key=f"rd{d['id']}"):
                with conn() as c:
                    c.execute("DELETE FROM doctors WHERE id=?", (d["id"],))
                st.rerun()
    st.caption("Removing a doctor stops new bookings. Existing appointments are kept.")


def admin_appointments():
    with conn() as c:
        counts = {r["status"]: r["n"] for r in c.execute(
            "SELECT status, COUNT(*) n FROM bookings GROUP BY status")}
    a, b, d = st.columns(3)
    a.metric("Pending", counts.get("Pending", 0))
    b.metric("Approved", counts.get("Approved", 0))
    d.metric("Rejected", counts.get("Rejected", 0))

    flt = st.radio("Show", ["Pending", "Approved", "Rejected", "All"], horizontal=True)
    q = st.text_input("Search by patient name or phone")
    sql = "SELECT * FROM bookings WHERE (patient LIKE ? OR phone LIKE ?)"
    args = [f"%{q}%", f"%{q}%"]
    if flt != "All":
        sql += " AND status=?"
        args.append(flt)
    with conn() as c:
        rows = c.execute(sql + " ORDER BY day, slot", args).fetchall()

    if not rows:
        st.info("Nothing here.")
    for r in rows:
        with st.container(border=True):
            st.markdown(f"{ICON[r['status']]} **{r['patient']}** · {r['phone']}  \n"
                        f"{r['doctor']}  \n{r['day']} at {r['slot']}"
                        + (f"  \nReason: {r['reason']}" if r["reason"] else ""))
            left, right = st.columns(2)
            if r["status"] == "Pending":
                if left.button("Approve", key=f"a{r['id']}", type="primary"):
                    set_status(r["id"], "Approved")
                if right.button("Reject", key=f"r{r['id']}"):
                    set_status(r["id"], "Rejected")
            elif r["status"] == "Approved":
                if right.button("Cancel appointment", key=f"x{r['id']}"):
                    set_status(r["id"], "Rejected")


nav = st.navigation([
    st.Page(book_page, title="Book appointment", icon="🏥", url_path="book", default=True),
    st.Page(status_page, title="My bookings", icon="📋", url_path="status"),
    st.Page(admin_page, title="Admin", icon="🔒", url_path="admin"),
])
nav.run()

