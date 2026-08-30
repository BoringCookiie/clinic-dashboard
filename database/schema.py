"""
SQLAlchemy ORM Schema definition for the Clinic Management Database.
Contains 13 relational tables representing clinic operations, clinical records, and billing.
"""

from datetime import datetime, date, time
from typing import List, Optional
from sqlalchemy import (
    String, Integer, Float, Date, Time, DateTime, ForeignKey, Text
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy ORM models."""
    pass


class Patient(Base):
    __tablename__ = "patients"

    patient_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    first_name: Mapped[str] = mapped_column(String(50), nullable=False)
    last_name: Mapped[str] = mapped_column(String(50), nullable=False)
    date_of_birth: Mapped[date] = mapped_column(Date, nullable=False)
    gender: Mapped[str] = mapped_column(String(20), nullable=False)
    phone: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    address: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    insurance_provider: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    insurance_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    registration_date: Mapped[date] = mapped_column(Date, nullable=False, default=date.today)
    blood_type: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)

    # Relationships
    appointments: Mapped[List["Appointment"]] = relationship("Appointment", back_populates="patient")
    visits: Mapped[List["Visit"]] = relationship("Visit", back_populates="patient")
    billings: Mapped[List["Billing"]] = relationship("Billing", back_populates="patient")


class Department(Base):
    __tablename__ = "departments"

    department_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    location: Mapped[str] = mapped_column(String(100), nullable=False)

    # Relationships
    doctors: Mapped[List["Doctor"]] = relationship("Doctor", back_populates="department")
    staff: Mapped[List["Staff"]] = relationship("Staff", back_populates="department")


class Doctor(Base):
    __tablename__ = "doctors"

    doctor_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    first_name: Mapped[str] = mapped_column(String(50), nullable=False)
    last_name: Mapped[str] = mapped_column(String(50), nullable=False)
    specialty: Mapped[str] = mapped_column(String(100), nullable=False)
    phone: Mapped[str] = mapped_column(String(30), nullable=False)
    email: Mapped[str] = mapped_column(String(100), nullable=False)
    hire_date: Mapped[date] = mapped_column(Date, nullable=False)
    department_id: Mapped[int] = mapped_column(Integer, ForeignKey("departments.department_id"), nullable=False)

    # Relationships
    department: Mapped["Department"] = relationship("Department", back_populates="doctors")
    appointments: Mapped[List["Appointment"]] = relationship("Appointment", back_populates="doctor")
    visits: Mapped[List["Visit"]] = relationship("Visit", back_populates="doctor")


class Staff(Base):
    __tablename__ = "staff"

    staff_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    first_name: Mapped[str] = mapped_column(String(50), nullable=False)
    last_name: Mapped[str] = mapped_column(String(50), nullable=False)
    role: Mapped[str] = mapped_column(String(100), nullable=False)
    department_id: Mapped[int] = mapped_column(Integer, ForeignKey("departments.department_id"), nullable=False)
    hire_date: Mapped[date] = mapped_column(Date, nullable=False)

    # Relationships
    department: Mapped["Department"] = relationship("Department", back_populates="staff")


class Appointment(Base):
    __tablename__ = "appointments"

    appointment_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    patient_id: Mapped[int] = mapped_column(Integer, ForeignKey("patients.patient_id"), nullable=False)
    doctor_id: Mapped[int] = mapped_column(Integer, ForeignKey("doctors.doctor_id"), nullable=False)
    appointment_date: Mapped[date] = mapped_column(Date, nullable=False)
    appointment_time: Mapped[time] = mapped_column(Time, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # scheduled, completed, cancelled, no-show
    reason_for_visit: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    patient: Mapped["Patient"] = relationship("Patient", back_populates="appointments")
    doctor: Mapped["Doctor"] = relationship("Doctor", back_populates="appointments")
    visit: Mapped[Optional["Visit"]] = relationship("Visit", back_populates="appointment", uselist=False)


class Visit(Base):
    __tablename__ = "visits"

    visit_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    appointment_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("appointments.appointment_id"), nullable=True)
    patient_id: Mapped[int] = mapped_column(Integer, ForeignKey("patients.patient_id"), nullable=False)
    doctor_id: Mapped[int] = mapped_column(Integer, ForeignKey("doctors.doctor_id"), nullable=False)
    visit_date: Mapped[date] = mapped_column(Date, nullable=False)
    symptoms: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    appointment: Mapped[Optional["Appointment"]] = relationship("Appointment", back_populates="visit")
    patient: Mapped["Patient"] = relationship("Patient", back_populates="visits")
    doctor: Mapped["Doctor"] = relationship("Doctor", back_populates="visits")
    diagnoses: Mapped[List["Diagnosis"]] = relationship("Diagnosis", back_populates="visit")
    prescriptions: Mapped[List["Prescription"]] = relationship("Prescription", back_populates="visit")
    lab_tests: Mapped[List["LabTest"]] = relationship("LabTest", back_populates="visit")
    billing: Mapped[Optional["Billing"]] = relationship("Billing", back_populates="visit", uselist=False)


class Diagnosis(Base):
    __tablename__ = "diagnoses"

    diagnosis_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    visit_id: Mapped[int] = mapped_column(Integer, ForeignKey("visits.visit_id"), nullable=False)
    diagnosis_code: Mapped[str] = mapped_column(String(20), nullable=False)
    diagnosis_name: Mapped[str] = mapped_column(String(150), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)  # Mild, Moderate, Severe

    # Relationships
    visit: Mapped["Visit"] = relationship("Visit", back_populates="diagnoses")


class Supplier(Base):
    """Supplier/vendor providing medications and medical supplies to the clinic."""
    __tablename__ = "suppliers"

    supplier_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False, unique=True)
    category: Mapped[str] = mapped_column(String(100), nullable=False)  # Pharmaceuticals, Medical Equipment, Lab Supplies, etc.
    contact_person: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    address: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    contract_start_date: Mapped[date] = mapped_column(Date, nullable=False)

    # Relationships
    medications: Mapped[List["Medication"]] = relationship("Medication", back_populates="supplier")


class Medication(Base):
    __tablename__ = "medications"

    medication_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    unit_price: Mapped[float] = mapped_column(Float, nullable=False)
    supplier_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("suppliers.supplier_id"), nullable=True)

    # Relationships
    prescriptions: Mapped[List["Prescription"]] = relationship("Prescription", back_populates="medication")
    supplier: Mapped[Optional["Supplier"]] = relationship("Supplier", back_populates="medications")


class Prescription(Base):
    __tablename__ = "prescriptions"

    prescription_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    visit_id: Mapped[int] = mapped_column(Integer, ForeignKey("visits.visit_id"), nullable=False)
    medication_id: Mapped[int] = mapped_column(Integer, ForeignKey("medications.medication_id"), nullable=False)
    dosage: Mapped[str] = mapped_column(String(50), nullable=False)
    duration_days: Mapped[int] = mapped_column(Integer, nullable=False)
    instructions: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Relationships
    visit: Mapped["Visit"] = relationship("Visit", back_populates="prescriptions")
    medication: Mapped["Medication"] = relationship("Medication", back_populates="prescriptions")


class LabTest(Base):
    __tablename__ = "lab_tests"

    test_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    visit_id: Mapped[int] = mapped_column(Integer, ForeignKey("visits.visit_id"), nullable=False)
    test_type: Mapped[str] = mapped_column(String(100), nullable=False)
    result: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    test_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # pending, completed

    # Relationships
    visit: Mapped["Visit"] = relationship("Visit", back_populates="lab_tests")


class Billing(Base):
    __tablename__ = "billing"

    invoice_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    visit_id: Mapped[int] = mapped_column(Integer, ForeignKey("visits.visit_id"), nullable=False)
    patient_id: Mapped[int] = mapped_column(Integer, ForeignKey("patients.patient_id"), nullable=False)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    insurance_covered_amount: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    patient_paid_amount: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    payment_status: Mapped[str] = mapped_column(String(20), nullable=False)  # paid, pending, overdue
    invoice_date: Mapped[date] = mapped_column(Date, nullable=False)

    # Relationships
    visit: Mapped["Visit"] = relationship("Visit", back_populates="billing")
    patient: Mapped["Patient"] = relationship("Patient", back_populates="billings")
    payments: Mapped[List["Payment"]] = relationship("Payment", back_populates="billing")


class Payment(Base):
    __tablename__ = "payments"

    payment_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    invoice_id: Mapped[int] = mapped_column(Integer, ForeignKey("billing.invoice_id"), nullable=False)
    payment_date: Mapped[date] = mapped_column(Date, nullable=False)
    payment_method: Mapped[str] = mapped_column(String(30), nullable=False)  # cash, card, insurance
    amount_paid: Mapped[float] = mapped_column(Float, nullable=False)

    # Relationships
    billing: Mapped["Billing"] = relationship("Billing", back_populates="payments")