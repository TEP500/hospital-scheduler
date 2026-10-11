"""Hospital Appointment Scheduler - Streamlit version."""
import sqlite3
from datetime import date

import streamlit as st

st.set_page_config(page_title="Clinic Scheduler", page_icon="🏥", layout="centered")

DB = "scheduler.db"
SLOTS = ["09:00", "09:30", "10:00", "10:30", "11:00", "11:30",
         "14:00", "14:30", "15:00", "15:30", "16:00", "16:30"]
DOCTORS = ["Dr. Asha Menon - Cardiology", "Dr. Rohan Verma - Orthopedics",
           "Dr. Priya Nair - Pediatrics", "Dr. Imran Qureshi - General Medicine",
           "Dr. Lena Fischer - Dermatology"]


def conn():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    c.execute("""CREATE TABLE IF NOT EXISTS appointments(
        id INTEGER PRIMARY KEY, patient TEXT NOT NULL, phone TEXT NOT NULL,
        doctor TEXT NOT NULL, day TEXT NOT NULL, slot TEXT NOT NULL, reason TEXT,
        UNIQUE(doctor, day, slot))""")
    return c


st.title("🏥 Clinic Scheduler")
tab_book, tab_list = st.tabs(["Book", "Appointments"])

with tab_book:
    doctor = st.selectbox("Doctor", DOCTORS)
    day = st.date_input("Date", min_value=date.today()).isoformat()
    with conn() as c:
        taken = {r["slot"] for r in c.execute(
            "SELECT slot FROM appointments WHERE doctor=? AND day=?", (doctor, day))}
    free = [s for s in SLOTS if s not in taken]

    if not free:
        st.warning("No times left on this date. Try another day.")
    else:
        with st.form("book"):
            slot = st.selectbox("Available times", free)
            patient = st.text_input("Patient name")
            phone = st.text_input("Phone number")
            reason = st.text_input("Reason for visit (optional)")
            if st.form_submit_button("Confirm appointment", type="primary"):
                if not patient.strip() or not phone.strip():
                    st.error("Enter the patient name and phone number.")
                else:
                    try:
                        with conn() as c:
                            c.execute("INSERT INTO appointments(patient,phone,doctor,day,slot,reason)"
                                      " VALUES (?,?,?,?,?,?)",
                                      (patient.strip(), phone.strip(), doctor, day, slot, reason.strip()))
                        st.success(f"Booked {patient} with {doctor} on {day} at {slot}.")
                    except sqlite3.IntegrityError:
                        st.error("That time was just taken. Pick another.")

with tab_list:
    q = st.text_input("Search by patient name or phone")
    with conn() as c:
        rows = c.execute("""SELECT * FROM appointments WHERE patient LIKE ? OR phone LIKE ?
                            ORDER BY day, slot""", (f"%{q}%", f"%{q}%")).fetchall()
    if not rows:
        st.info("No appointments found. Book one in the Book tab.")
    for r in rows:
        with st.container(border=True):
            st.markdown(f"**{r['patient']}** · {r['phone']}  \n"
                        f"{r['doctor']}  \n{r['day']} at {r['slot']}"
                        + (f"  \nReason: {r['reason']}" if r["reason"] else ""))
            if st.button("Cancel appointment", key=f"c{r['id']}"):
                with conn() as c:
                    c.execute("DELETE FROM appointments WHERE id=?", (r["id"],))
                st.rerun()
