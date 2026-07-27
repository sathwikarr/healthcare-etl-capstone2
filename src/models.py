"""
Lightweight data classes representing single domain entities.
These are used for row-level representations / type safety, separate
from the bulk DataFrame operations in validation.py and transform.py.
"""

from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional


@dataclass
class Patient:
    patient_id: int
    patient_name: Optional[str]
    dob: Optional[date]
    gender: Optional[str]

    def age(self, as_of: Optional[date] = None) -> Optional[int]:
        """Compute age in years as of a given date (defaults to today)."""
        if self.dob is None:
            return None
        as_of = as_of or date.today()
        years = as_of.year - self.dob.year
        if (as_of.month, as_of.day) < (self.dob.month, self.dob.day):
            years -= 1
        return years

    @classmethod
    def from_row(cls, row) -> "Patient":
        """Build a Patient from a pandas Series (one row of the cleaned patients df)."""
        dob = row["dob"]
        dob_date = dob.date() if isinstance(dob, (datetime, )) and not pd_isnull(dob) else None
        return cls(
            patient_id=int(row["patient_id"]),
            patient_name=row["patient_name"] if not pd_isnull(row["patient_name"]) else None,
            dob=dob_date,
            gender=row["gender"] if not pd_isnull(row["gender"]) else None,
        )


@dataclass
class Appointment:
    appointment_id: int
    patient_id: Optional[int]
    doctor_id: int
    start_time: Optional[datetime]
    end_time: Optional[datetime]

    def duration_minutes(self) -> Optional[float]:
        """Compute visit duration in minutes, or None if either timestamp is missing."""
        if self.start_time is None or self.end_time is None:
            return None
        return (self.end_time - self.start_time).total_seconds() / 60

    @classmethod
    def from_row(cls, row) -> "Appointment":
        """Build an Appointment from a pandas Series (one row of the cleaned appointments df)."""
        return cls(
            appointment_id=int(row["appointment_id"]),
            patient_id=int(row["patient_id"]) if not pd_isnull(row["patient_id"]) else None,
            doctor_id=int(row["doctor_id"]),
            start_time=row["start_time"] if not pd_isnull(row["start_time"]) else None,
            end_time=row["end_time"] if not pd_isnull(row["end_time"]) else None,
        )


def pd_isnull(value) -> bool:
    """Local null check avoiding a hard pandas import dependency in the dataclass defs."""
    import pandas as pd
    return pd.isnull(value)