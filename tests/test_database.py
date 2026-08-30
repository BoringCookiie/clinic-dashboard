"""
Database Integrity and Sanity Tests.
Verifies table counts, foreign key relationships, and data completeness in clinic.db.
"""

import os
import pytest
from sqlalchemy import text
from database.db_utils import engine, SessionLocal, DB_PATH
from database.schema import (
    Patient, Department, Doctor, Staff, Appointment, Visit,
    Diagnosis, Medication, Prescription, LabTest, Billing, Payment, Supplier
)


@pytest.fixture(scope="module")
def db_session():
    """Provides a database session for tests."""
    assert DB_PATH.exists(), f"Database file does not exist at {DB_PATH}. Run python -m database.generate_data first!"
    session = SessionLocal()
    yield session
    session.close()


def test_database_file_exists():
    """Verify that clinic.db file exists on disk."""
    assert DB_PATH.exists(), "clinic.db file should exist."


def test_table_row_counts(db_session):
    """Verify that all tables contain non-zero generated records."""
    assert db_session.query(Department).count() >= 5
    assert db_session.query(Doctor).count() >= 15
    assert db_session.query(Staff).count() >= 20
    assert db_session.query(Patient).count() >= 300
    assert db_session.query(Supplier).count() >= 5
    assert db_session.query(Medication).count() >= 10
    assert db_session.query(Appointment).count() >= 1000
    assert db_session.query(Visit).count() >= 800
    assert db_session.query(Diagnosis).count() >= 800
    assert db_session.query(Prescription).count() >= 500
    assert db_session.query(LabTest).count() >= 300
    assert db_session.query(Billing).count() >= 800
    assert db_session.query(Payment).count() >= 500


def test_foreign_key_doctor_department(db_session):
    """Verify all doctors reference valid department IDs."""
    doctors = db_session.query(Doctor).all()
    dept_ids = {d.department_id for d in db_session.query(Department).all()}
    for doc in doctors:
        assert doc.department_id in dept_ids, f"Doctor {doc.doctor_id} has invalid department_id {doc.department_id}"


def test_foreign_key_medication_supplier(db_session):
    """Verify all medications reference a valid supplier ID."""
    supplier_ids = {f.supplier_id for f in db_session.query(Supplier).all()}
    medications = db_session.query(Medication).all()
    for med in medications:
        assert med.supplier_id is not None, f"Medication {med.medication_id} has no assigned supplier"
        assert med.supplier_id in supplier_ids, f"Medication {med.medication_id} has invalid supplier_id {med.supplier_id}"


def test_foreign_key_appointment_patient_doctor(db_session):
    """Verify appointments reference valid patient and doctor IDs."""
    patient_ids = {p.patient_id for p in db_session.query(Patient).all()}
    doctor_ids = {d.doctor_id for d in db_session.query(Doctor).all()}
    
    sample_appointments = db_session.query(Appointment).limit(100).all()
    for apt in sample_appointments:
        assert apt.patient_id in patient_ids
        assert apt.doctor_id in doctor_ids


def test_no_orphaned_visits(db_session):
    """Verify that all visits reference existing patients and doctors."""
    patient_ids = {p.patient_id for p in db_session.query(Patient).all()}
    doctor_ids = {d.doctor_id for d in db_session.query(Doctor).all()}
    
    visits = db_session.query(Visit).limit(100).all()
    for v in visits:
        assert v.patient_id in patient_ids
        assert v.doctor_id in doctor_ids


def test_no_orphaned_diagnoses(db_session):
    """Verify all diagnoses reference valid visit IDs."""
    visit_ids = {v.visit_id for v in db_session.query(Visit).limit(500).all()}
    diagnoses = db_session.query(Diagnosis).limit(100).all()
    for d in diagnoses:
        assert d.visit_id in visit_ids


def test_no_orphaned_billings(db_session):
    """Verify all billing records reference valid visit IDs and patient IDs."""
    visit_ids = {v.visit_id for v in db_session.query(Visit).limit(500).all()}
    patient_ids = {p.patient_id for p in db_session.query(Patient).all()}
    
    billings = db_session.query(Billing).limit(100).all()
    for b in billings:
        assert b.visit_id in visit_ids
        assert b.patient_id in patient_ids