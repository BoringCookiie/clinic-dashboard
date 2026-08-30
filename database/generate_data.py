"""
Synthetic Data Generation Script for Clinic Database.
Populates SQLite database with realistic, correlated clinic data:
patients, departments, doctors, staff, suppliers, appointments, visits, diagnoses,
medications, prescriptions, lab tests, billing, and payments.

Uses Faker, numpy, and random seeds for 100% reproducibility and idempotency.
"""

import random
from datetime import datetime, date, timedelta, time
import numpy as np
import pandas as pd
from faker import Faker
from sqlalchemy.orm import Session

from database.db_utils import init_db, SessionLocal
from database.schema import (
    Patient, Department, Doctor, Staff, Appointment, Visit,
    Diagnosis, Medication, Prescription, LabTest, Billing, Payment, Supplier
)

# Seed for reproducibility
SEED = 42
random.seed(SEED)
np.random.seed(SEED)
fake = Faker()
Faker.seed(SEED)


def generate_departments(session: Session) -> list[Department]:
    dept_data = [
        {"name": "General Practice", "location": "Building A, Floor 1"},
        {"name": "Cardiology", "location": "Building B, Floor 2"},
        {"name": "Pediatrics", "location": "Building A, Floor 2"},
        {"name": "Orthopedics", "location": "Building C, Floor 1"},
        {"name": "Pulmonology", "location": "Building B, Floor 3"},
        {"name": "Dermatology", "location": "Building C, Floor 2"},
    ]
    departments = [Department(**d) for d in dept_data]
    session.add_all(departments)
    session.flush()
    return departments


def generate_doctors(session: Session, departments: list[Department]) -> list[Doctor]:
    specialties = {
        "General Practice": ["Family Medicine", "Internal Medicine", "General Practitioner"],
        "Cardiology": ["Interventional Cardiology", "General Cardiology", "Electrophysiology"],
        "Pediatrics": ["General Pediatrics", "Pediatric Cardiology"],
        "Orthopedics": ["Orthopedic Surgery", "Sports Medicine", "Joint Replacement"],
        "Pulmonology": ["Pulmonology", "Critical Care Medicine"],
        "Dermatology": ["General Dermatology", "Cosmetic Dermatology"]
    }
    
    doctors = []
    hire_start = date(2018, 1, 1)
    
    for dept in departments:
        # Create 3 doctors per department = 18 doctors
        for _ in range(3):
            fn = fake.first_name()
            ln = fake.last_name()
            spec = random.choice(specialties[dept.name])
            h_date = fake.date_between(start_date=hire_start, end_date=date(2023, 12, 31))
            doc = Doctor(
                first_name=fn,
                last_name=ln,
                specialty=spec,
                phone=fake.phone_number()[:25],
                email=f"dr.{fn.lower()}.{ln.lower()}@smartclinic.com",
                hire_date=h_date,
                department_id=dept.department_id
            )
            doctors.append(doc)
            
    session.add_all(doctors)
    session.flush()
    return doctors


def generate_staff(session: Session, departments: list[Department]) -> list[Staff]:
    roles = ["Nurse Practitioner", "Registered Nurse", "Medical Assistant", "Receptionist", "Lab Technician"]
    staff_members = []
    
    for dept in departments:
        # Create 4 staff per department = 24 staff members
        for _ in range(4):
            fn = fake.first_name()
            ln = fake.last_name()
            role = random.choice(roles)
            h_date = fake.date_between(start_date=date(2019, 1, 1), end_date=date(2024, 1, 1))
            st = Staff(
                first_name=fn,
                last_name=ln,
                role=role,
                department_id=dept.department_id,
                hire_date=h_date
            )
            staff_members.append(st)
            
    session.add_all(staff_members)
    session.flush()
    return staff_members


def generate_patients(session: Session, count: int = 400) -> list[Patient]:
    blood_types = ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"]
    insurance_providers = ["BlueCross", "Aetna", "UnitedHealth", "Cigna", "Humana", "Medicare", "Medicaid", None]
    
    patients = []
    start_reg = date(2024, 1, 1)
    end_reg = date(2026, 7, 31)

    for i in range(count):
        gender = random.choice(["Male", "Female"])
        fn = fake.first_name_male() if gender == "Male" else fake.first_name_female()
        ln = fake.last_name()
        dob = fake.date_of_birth(minimum_age=1, maximum_age=85)
        
        # Introduce mild realistic messiness (e.g. 5% missing email/phone, occasional missing insurance)
        has_email = random.random() > 0.06
        has_phone = random.random() > 0.04
        provider = random.choice(insurance_providers)
        ins_num = f"INS-{random.randint(100000, 999999)}" if provider else None
        
        patient = Patient(
            first_name=fn,
            last_name=ln,
            date_of_birth=dob,
            gender=gender,
            phone=fake.phone_number()[:25] if has_phone else None,
            email=f"{fn.lower()}.{ln.lower()}{random.randint(10,99)}@{fake.free_email_domain()}" if has_email else None,
            address=fake.street_address(),
            insurance_provider=provider,
            insurance_number=ins_num,
            registration_date=fake.date_between(start_date=start_reg, end_date=end_reg),
            blood_type=random.choice(blood_types)
        )
        patients.append(patient)
        
    # Duplicate-looking patient records (realistic messiness)
    if count >= 10:
        p_dup1 = Patient(
            first_name=patients[0].first_name,
            last_name=patients[0].last_name,
            date_of_birth=patients[0].date_of_birth,
            gender=patients[0].gender,
            phone=patients[0].phone,
            email=patients[0].email,
            address="123 Alternate St",
            insurance_provider="BlueCross",
            insurance_number="INS-999111",
            registration_date=date(2025, 3, 15),
            blood_type=patients[0].blood_type
        )
        patients.append(p_dup1)

    session.add_all(patients)
    session.flush()
    return patients


def generate_suppliers(session: Session) -> list[Supplier]:
    suppliers_data = [
        {"name": "PharmaCorp Distribution", "category": "Pharmaceuticals", "contact_person": "Nadia Alaoui", "start": date(2019, 3, 1)},
        {"name": "MediSupply International", "category": "Pharmaceuticals", "contact_person": "Karim Bensaid", "start": date(2020, 6, 15)},
        {"name": "BioGen Pharma Solutions", "category": "Pharmaceuticals", "contact_person": "Sophie Lambert", "start": date(2021, 1, 10)},
        {"name": "MedEquip Technologies", "category": "Medical Equipment", "contact_person": "Youssef El Amrani", "start": date(2018, 9, 5)},
        {"name": "PrecisionLab Instruments", "category": "Lab Supplies", "contact_person": "Amina Cherkaoui", "start": date(2022, 2, 20)},
        {"name": "CleanCare Medical Supplies", "category": "Consumables & PPE", "contact_person": "Thomas Weber", "start": date(2020, 11, 1)},
        {"name": "OrthoTech Devices", "category": "Medical Equipment", "contact_person": "Laila Bouzidi", "start": date(2023, 4, 12)},
        {"name": "GlobalMeds Wholesale", "category": "Pharmaceuticals", "contact_person": "Hassan Idrissi", "start": date(2019, 7, 22)},
    ]

    suppliers = []
    for f in suppliers_data:
        suppliers.append(Supplier(
            name=f["name"],
            category=f["category"],
            contact_person=f["contact_person"],
            phone=fake.phone_number()[:25],
            email=f["name"].lower().replace(" ", ".").replace(",", "") + "@supplier.com",
            address=fake.street_address(),
            contract_start_date=f["start"]
        ))

    session.add_all(suppliers)
    session.flush()
    return suppliers


def generate_medications(session: Session, suppliers: list[Supplier]) -> list[Medication]:
    meds_data = [
        {"name": "Metformin 500mg", "category": "Antidiabetic", "unit_price": 15.50},
        {"name": "Insulin Glargine 100U/ml", "category": "Antidiabetic", "unit_price": 65.00},
        {"name": "Lisinopril 10mg", "category": "Antihypertensive", "unit_price": 12.00},
        {"name": "Amlodipine 5mg", "category": "Antihypertensive", "unit_price": 14.25},
        {"name": "Losartan 50mg", "category": "Antihypertensive", "unit_price": 18.00},
        {"name": "Amoxicillin 500mg", "category": "Antibiotic", "unit_price": 22.00},
        {"name": "Azithromycin 250mg", "category": "Antibiotic", "unit_price": 28.50},
        {"name": "Albuterol Inhaler", "category": "Bronchodilator", "unit_price": 45.00},
        {"name": "Fluticasone Nasal Spray", "category": "Corticosteroid", "unit_price": 32.00},
        {"name": "Ibuprofen 400mg", "category": "Analgesic / NSAID", "unit_price": 8.00},
        {"name": "Acetaminophen 500mg", "category": "Analgesic", "unit_price": 6.50},
        {"name": "Omeprazole 20mg", "category": "Gastroprotective", "unit_price": 19.99},
        {"name": "Atorvastatin 20mg", "category": "Statin / Lipid Regulator", "unit_price": 25.00},
        {"name": "Cetirizine 10mg", "category": "Antihistamine", "unit_price": 11.50},
        {"name": "Hydrocortisone Cream 1%", "category": "Topical Corticosteroid", "unit_price": 13.00},
    ]
    pharma_suppliers = [f for f in suppliers if f.category == "Pharmaceuticals"] or suppliers
    medications = [Medication(**m, supplier_id=random.choice(pharma_suppliers).supplier_id) for m in meds_data]
    session.add_all(medications)
    session.flush()
    return medications


def generate_clinical_activity(
    session: Session,
    patients: list[Patient],
    doctors: list[Doctor],
    medications: list[Medication],
    num_appointments: int = 3800
):
    # Medical knowledge dictionary mapping diagnoses to realistic department, symptoms, meds, lab tests
    diagnoses_catalog = [
        {
            "code": "E11.9", "name": "Type 2 Diabetes Mellitus", "dept": "General Practice",
            "symptoms": "Increased thirst, frequent urination, unexplained fatigue, blurred vision.",
            "med_name": "Metformin 500mg", "lab": "HbA1c Test"
        },
        {
            "code": "I10", "name": "Essential Primary Hypertension", "dept": "Cardiology",
            "symptoms": "Mild headache, dizziness, shortness of breath on exertion, high BP reading.",
            "med_name": "Lisinopril 10mg", "lab": "Lipid Panel"
        },
        {
            "code": "J06.9", "name": "Acute Upper Respiratory Infection", "dept": "Pulmonology",
            "symptoms": "Sore throat, nasal congestion, sneezing, low-grade fever, cough.",
            "med_name": "Amoxicillin 500mg", "lab": "Rapid Throat Swab"
        },
        {
            "code": "J20.9", "name": "Acute Bronchitis", "dept": "Pulmonology",
            "symptoms": "Persistent hacking cough, chest discomfort, fatigue, mild wheezing.",
            "med_name": "Azithromycin 250mg", "lab": "Chest X-Ray"
        },
        {
            "code": "J45.909", "name": "Asthma Unspecified", "dept": "Pulmonology",
            "symptoms": "Shortness of breath, chest tightness, audible wheezing during respiration.",
            "med_name": "Albuterol Inhaler", "lab": "Spirometry Pulmonary Function Test"
        },
        {
            "code": "M19.90", "name": "Osteoarthritis Unspecified", "dept": "Orthopedics",
            "symptoms": "Joint stiffness in knee and hip, localized swelling, pain after movement.",
            "med_name": "Ibuprofen 400mg", "lab": "Joint X-Ray"
        },
        {
            "code": "M54.5", "name": "Low Back Pain", "dept": "Orthopedics",
            "symptoms": "Dull ache in lower back, muscle spasm, limited lumbar range of motion.",
            "med_name": "Ibuprofen 400mg", "lab": "Lumbar Spine X-Ray"
        },
        {
            "code": "N39.0", "name": "Urinary Tract Infection", "dept": "General Practice",
            "symptoms": "Burning sensation during urination, pelvic pain, frequent urge to urinate.",
            "med_name": "Amoxicillin 500mg", "lab": "Urinalysis & Culture"
        },
        {
            "code": "H66.90", "name": "Otitis Media Unspecified", "dept": "Pediatrics",
            "symptoms": "Ear pain, pulling at ear, irritability, fluid discharge, mild fever.",
            "med_name": "Amoxicillin 500mg", "lab": "Otoscopic Exam"
        },
        {
            "code": "K21.9", "name": "Gastro-esophageal Reflux Disease (GERD)", "dept": "General Practice",
            "symptoms": "Heartburn, acid regurgitation, difficulty swallowing, chest pain after meals.",
            "med_name": "Omeprazole 20mg", "lab": "Upper Endoscopy"
        },
        {
            "code": "L70.0", "name": "Acne Vulgaris", "dept": "Dermatology",
            "symptoms": "Facial papules, pustules, comedones, localized skin inflammation.",
            "med_name": "Hydrocortisone Cream 1%", "lab": "Dermatological Assessment"
        },
        {
            "code": "E78.5", "name": "Hyperlipidemia", "dept": "Cardiology",
            "symptoms": "Asymptomatic, detected during routine lipid screening.",
            "med_name": "Atorvastatin 20mg", "lab": "Comprehensive Lipid Panel"
        },
        {
            "code": "J30.9", "name": "Allergic Rhinitis", "dept": "General Practice",
            "symptoms": "Watery eyes, sneezing fits, runny nose, itchy throat.",
            "med_name": "Cetirizine 10mg", "lab": "Allergy Skin Prick Test"
        },
    ]

    med_map = {m.name: m for m in medications}
    doc_by_dept = {}
    for doc in doctors:
        doc_by_dept.setdefault(doc.department.name, []).append(doc)

    start_date = date(2024, 8, 1)
    end_date = date(2026, 8, 1)
    total_days = (end_date - start_date).days

    reasons = [
        "Routine checkup and consultation",
        "Follow-up visit for ongoing symptoms",
        "Acute pain evaluation",
        "Prescription renewal request",
        "Annual wellness exam",
        "Lab results review and consultation"
    ]

    statuses = ["completed", "completed", "completed", "completed", "completed", "completed", "completed", "no-show", "cancelled"]

    business_hours = [
        time(8, 30), time(9, 0), time(9, 30), time(10, 0), time(10, 30),
        time(11, 0), time(11, 30), time(13, 0), time(13, 30), time(14, 0),
        time(14, 30), time(15, 0), time(15, 30), time(16, 0), time(16, 30)
    ]

    appointments = []
    visits = []
    diagnoses = []
    prescriptions = []
    lab_tests = []
    billings = []
    payments = []

    for _ in range(num_appointments):
        patient = random.choice(patients)
        
        # Pick appointment date with winter seasonal bias for respiratory symptoms
        day_offset = random.randint(0, total_days)
        apt_date = start_date + timedelta(days=day_offset)
        
        # Skip Sundays (ensure weekday clustering)
        if apt_date.weekday() == 6:
            apt_date += timedelta(days=1)

        # Seasonal pattern: increase probability of respiratory/general practice in winter (Dec-Feb)
        is_winter = apt_date.month in [12, 1, 2]
        if is_winter and random.random() < 0.45:
            diag_choice = random.choice([
                d for d in diagnoses_catalog if d["dept"] in ["Pulmonology", "General Practice", "Pediatrics"]
            ])
        else:
            diag_choice = random.choice(diagnoses_catalog)

        target_dept = diag_choice["dept"]
        assigned_doc = random.choice(doc_by_dept.get(target_dept, doctors))
        apt_time = random.choice(business_hours)
        status = random.choice(statuses)

        apt = Appointment(
            patient_id=patient.patient_id,
            doctor_id=assigned_doc.doctor_id,
            appointment_date=apt_date,
            appointment_time=apt_time,
            status=status,
            reason_for_visit=random.choice(reasons),
            created_at=datetime.combine(apt_date - timedelta(days=random.randint(1, 10)), apt_time)
        )
        appointments.append(apt)

    session.add_all(appointments)
    session.flush()

    # Generate Visits ONLY for Completed Appointments
    for apt in appointments:
        if apt.status != "completed":
            continue

        visit = Visit(
            appointment_id=apt.appointment_id,
            patient_id=apt.patient_id,
            doctor_id=apt.doctor_id,
            visit_date=apt.appointment_date,
            symptoms=fake.sentence(nb_words=8),
            notes=f"Patient presented with complaints. Physician recommended treatment plan."
        )
        visits.append(visit)

    session.add_all(visits)
    session.flush()

    # Generate Diagnoses, Prescriptions, Lab Tests, Billing for Visits
    for visit in visits:
        # Match diagnosis catalog
        diag_item = random.choice(diagnoses_catalog)
        severity = random.choice(["Mild", "Moderate", "Severe"])
        
        diag = Diagnosis(
            visit_id=visit.visit_id,
            diagnosis_code=diag_item["code"],
            diagnosis_name=diag_item["name"],
            severity=severity
        )
        diagnoses.append(diag)

        # Prescription (80% of completed visits get a prescription)
        if random.random() < 0.80:
            med_obj = med_map.get(diag_item["med_name"], random.choice(medications))
            rx = Prescription(
                visit_id=visit.visit_id,
                medication_id=med_obj.medication_id,
                dosage="1 tablet daily" if "mg" in med_obj.name else "Use as directed",
                duration_days=random.choice([7, 10, 14, 30, 90]),
                instructions="Take with water after meals."
            )
            prescriptions.append(rx)

        # Lab Test (45% of completed visits get a lab test)
        if random.random() < 0.45:
            lab_status = random.choice(["completed", "completed", "completed", "pending"])
            lab = LabTest(
                visit_id=visit.visit_id,
                test_type=diag_item["lab"],
                result="Within Normal Limits" if lab_status == "completed" else None,
                test_date=visit.visit_date,
                status=lab_status
            )
            lab_tests.append(lab)

        # Billing & Payments
        consult_fee = float(random.choice([100, 120, 150, 200, 250]))
        has_insurance = random.random() < 0.75
        insurance_cov = round(consult_fee * random.choice([0.5, 0.7, 0.8, 0.9]), 2) if has_insurance else 0.0
        patient_due = round(consult_fee - insurance_cov, 2)

        # Payment status breakdown: 70% paid, 20% pending, 10% overdue
        pay_status = random.choice(["paid", "paid", "paid", "paid", "paid", "paid", "paid", "pending", "pending", "overdue"])
        
        if pay_status == "paid":
            patient_paid = patient_due
        elif pay_status == "pending":
            patient_paid = 0.0
        else:  # overdue
            patient_paid = 0.0

        bill = Billing(
            visit_id=visit.visit_id,
            patient_id=visit.patient_id,
            amount=consult_fee,
            insurance_covered_amount=insurance_cov,
            patient_paid_amount=patient_paid,
            payment_status=pay_status,
            invoice_date=visit.visit_date
        )
        billings.append(bill)

    session.add_all(diagnoses)
    session.add_all(prescriptions)
    session.add_all(lab_tests)
    session.add_all(billings)
    session.flush()

    # Generate Payments for Billing records
    for bill in billings:
        if bill.payment_status == "paid" and bill.patient_paid_amount > 0:
            pay = Payment(
                invoice_id=bill.invoice_id,
                payment_date=bill.invoice_date + timedelta(days=random.randint(0, 5)),
                payment_method=random.choice(["card", "card", "insurance", "cash"]),
                amount_paid=bill.patient_paid_amount
            )
            payments.append(pay)

    session.add_all(payments)
    session.flush()


def generate_all():
    """
    Main data generation function. Resets the DB schema and populates clean synthetic data.
    """
    print("=" * 60)
    print("Starting Synthetic Clinic Database Generation...")
    print("=" * 60)

    # Re-initialize DB tables cleanly
    init_db(reset=True)

    session = SessionLocal()
    try:
        print("[1/6] Creating Departments...")
        departments = generate_departments(session)
        
        print("[2/6] Creating Doctors and Staff...")
        doctors = generate_doctors(session, departments)
        staff = generate_staff(session, departments)

        print("[3/6] Creating Patients...")
        patients = generate_patients(session, count=400)

        print("[4/6] Creating Suppliers...")
        suppliers = generate_suppliers(session)

        print("[5/6] Creating Medications...")
        medications = generate_medications(session, suppliers)

        print("[6/6] Generating Appointments, Visits, Diagnoses, Prescriptions, Lab Tests, Billing & Payments...")
        generate_clinical_activity(session, patients, doctors, medications, num_appointments=3800)

        session.commit()
        print("\n" + "=" * 60)
        print("DATABASE GENERATION COMPLETE!")
        print("=" * 60)

        # Print Row Count Summary
        tables = [
            ("departments", Department),
            ("doctors", Doctor),
            ("staff", Staff),
            ("patients", Patient),
            ("suppliers", Supplier),
            ("medications", Medication),
            ("appointments", Appointment),
            ("visits", Visit),
            ("diagnoses", Diagnosis),
            ("prescriptions", Prescription),
            ("lab_tests", LabTest),
            ("billing", Billing),
            ("payments", Payment),
        ]
        
        print("\nSummary of Generated Database Records:")
        print("-" * 45)
        for t_name, model_cls in tables:
            count = session.query(model_cls).count()
            print(f"  • {t_name:<20}: {count:>6} rows")
        print("-" * 45)

    except Exception as e:
        session.rollback()
        print(f"Error during data generation: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    generate_all()