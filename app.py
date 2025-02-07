import streamlit as st
import pandas as pd
import numpy as np
import random
from datetime import datetime, timedelta, date

# Import the CP-SAT solver from OR-Tools.
from ortools.sat.python import cp_model

# Initialize session state variables if not set.
if "master_schedule" not in st.session_state:
    st.session_state.master_schedule = None
if "nurse_names" not in st.session_state:
    st.session_state.nurse_names = None
if "start_date" not in st.session_state:
    st.session_state.start_date = None

st.title("Nurse Shift Scheduling Wheel (Rotation Model)")

st.markdown(
    """
This app creates a 12‑week cyclical schedule for 12 nurses—but with a twist. Instead of assigning a full 84‑day schedule to each nurse independently, we generate one master 84‑day schedule (covering 12 weeks) and then assign each nurse a cyclic rotation of that schedule. In other words:

- **Nurse Week 1:** Uses the master schedule as-is.
- **Nurse Week 2:** Uses the master schedule shifted by 7 days.
- **… etc.**

All of the original constraints are maintained:
- **Daily staffing:** Exactly **3 Day shifts** and **2 Night shifts** are worked each day overall.
- **At most one shift per day** for each nurse.
- **No more than 3 consecutive work days** (any 4‐day block has at most 3 shifts).
- **Weekend pairing:** If a nurse works Saturday then the following Sunday must be worked (and vice–versa).
- **Rest after a Night shift:** A Night shift cannot be immediately followed by a Day shift.
- **Maximum consecutive off‑shifts:** (Every block of 5 consecutive days must include at least one shift – i.e. no more than 9 off–shift periods.)
- **Fair distribution:** Each nurse works exactly **35 shifts** in 84 days.

Two views are provided. In the **Overall Schedule Grid** (the “current view”) the rows are overall calendar days and the columns are nurse names. In the **Personal Schedule View** you select a nurse and see that nurse’s 12‑week schedule arranged by week (rows) and weekday (columns).

_Enter your settings and nurse names below, then click “Generate Schedule.”_
    """
)

st.header("Schedule Settings")

# The overall schedule always covers 12 weeks (84 days)
num_weeks = 12
days_per_week = 7
horizon = num_weeks * days_per_week  # 84 days

# Choose the overall start date.
start_date = st.date_input("Select the schedule start date", value=date.today())

# Optionally toggle enforcement of the maximum rest (off‐shift) constraint.
enforce_max_rest = st.checkbox(
    "Enforce maximum consecutive off‑shift periods (9 off‑shifts) constraint",
    value=True
)

# ----- Nurse Information -----
st.header("Step 1. Enter Nurse Names (12 total)")
# (The nurse names now indicate the week the nurse starts on.)
nurse_names = []
for i in range(12):
    name = st.text_input(f"Nurse Week {i+1} Name", key=f"name_{i}")
    nurse_names.append(name.strip())

if st.button("Generate Schedule"):
    # Validate that all 12 names are provided.
    valid_names = [name for name in nurse_names if name != ""]
    if len(valid_names) != 12:
        st.error("Please enter a name for each of the 12 nurses.")
    else:
        st.info("Building schedule – please wait...")

        # ----- Build the CP-SAT model using a master schedule pattern.
        # In the master schedule we have 84 days. For each day d we define two boolean variables:
        #   y[d,0] = 1 means a Day shift is worked on day d.
        #   y[d,1] = 1 means a Night shift is worked on day d.
        #
        # (If both are 0, that day is off.)
        #
        # Overall, a nurse’s personal schedule will be exactly the master schedule rotated by a multiple of 7 days.
        # (For nurse n, on overall day d, the assignment is given by y[(d - n*7) mod 84].)
        
        # Parameters for shifts per overall day:
        required_day_shifts = 3
        required_night_shifts = 2

        model = cp_model.CpModel()

        # Create master schedule decision variables: y[d,s] for d in 0..83 and s in {0,1}.
        y = {}
        for d in range(horizon):
            for s in [0, 1]:
                y[d, s] = model.NewBoolVar(f"y_d{d}_s{s}")

        # (1) At most one shift per day in the master schedule.
        for d in range(horizon):
            model.Add(y[d, 0] + y[d, 1] <= 1)

        # (2) Fair distribution: exactly 35 shifts in 84 days.
        model.Add(sum(y[d, 0] + y[d, 1] for d in range(horizon)) == 35)

        # (3) Daily staffing constraints – using a little math:
        #     Each overall day d (for any nurse’s rotation) will come from one residue r modulo 7.
        #     In fact, for any overall day with weekday r, the set of master schedule positions used
        #     is exactly the set { r, r+7, r+14, …, r+77 }.
        #     Therefore, for each r = 0,...,6 we require:
        #         sum_{d in group_r} y[d, 0] == required_day_shifts (3)
        #         sum_{d in group_r} y[d, 1] == required_night_shifts (2)
        for r in range(7):
            group = [r + 7 * w for w in range(num_weeks) if r + 7 * w < horizon]
            model.Add(sum(y[d, 0] for d in group) == required_day_shifts)
            model.Add(sum(y[d, 1] for d in group) == required_night_shifts)

        # Helper: For a given nurse n (0-indexed) and her personal day d (0..83),
        # the corresponding index in the master schedule is:
        def master_index(n, d):
            return (d - n * days_per_week) % horizon

        # (4) Nurse-specific constraints.
        # For every nurse, the personal schedule is the master schedule rotated by n*7 days.
        # We now add the constraints “per nurse” by referring to the appropriate master schedule entries.
        for n in range(12):
            # (4a) No more than 3 consecutive work days.
            # For every block of 4 consecutive personal days (d, d+1, d+2, d+3) in nurse n’s schedule:
            for d in range(horizon - 3):
                indices = [master_index(n, d + i) for i in range(4)]
                model.Add(sum(y[idx, 0] + y[idx, 1] for idx in indices) <= 3)

            # (4b) Rest after a Night shift: If nurse n works a Night shift on day d,
            # then she cannot work a Day shift on day d+1.
            for d in range(horizon - 1):
                model.Add(y[master_index(n, d), 1] + y[master_index(n, d + 1), 0] <= 1)

            # (4c) Weekend pairing:
            # For each personal day d that is a Saturday (and d+1 is Sunday), if nurse n works that Saturday,
            # she must also work on the following Sunday (and vice versa).
            for d in range(horizon - 1):
                nurse_day = start_date + timedelta(days=n * days_per_week + d)
                if nurse_day.weekday() == 5:  # Saturday
                    next_day = nurse_day + timedelta(days=1)
                    if next_day.weekday() == 6:  # Sunday
                        model.Add(
                            y[master_index(n, d), 0] + y[master_index(n, d), 1]
                            ==
                            y[master_index(n, d + 1), 0] + y[master_index(n, d + 1), 1]
                        )

            # (4d) Maximum consecutive off–shift periods:
            # In any block of 5 consecutive personal days, at least one shift must be worked.
            if enforce_max_rest:
                for d in range(horizon - 4):
                    indices = [master_index(n, d + i) for i in range(5)]
                    model.Add(sum(y[idx, 0] + y[idx, 1] for idx in indices) >= 1)

        # (5) Introduce a random objective to help the solver choose among many solutions.
        rand_obj = []
        for d in range(horizon):
            for s in [0, 1]:
                coeff = random.randint(0, 10)
                rand_obj.append(coeff * y[d, s])
        model.Maximize(sum(rand_obj))

        # Solve the model.
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = 60.0
        solver.parameters.random_seed = random.randint(0, 1000000)
        status = solver.Solve(model)

        if status in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
            st.success("Schedule generated successfully!")

            # Build the master schedule pattern (a list of 84 entries, one per day).
            master_pattern = []
            for d in range(horizon):
                if solver.Value(y[d, 0]) == 1:
                    master_pattern.append("D")
                elif solver.Value(y[d, 1]) == 1:
                    master_pattern.append("N")
                else:
                    master_pattern.append("")
            st.session_state.master_schedule = master_pattern
            st.session_state.nurse_names = valid_names
            st.session_state.start_date = start_date
        else:
            st.error("No feasible schedule was found. Please adjust parameters and try again.")

###############################################################################
#                      DISPLAY OF THE SCHEDULE(S)                           #
###############################################################################

if st.session_state.master_schedule is not None:
    master_pattern = st.session_state.master_schedule
    valid_names = st.session_state.nurse_names
    start_date = st.session_state.start_date
    horizon = 84  # 12 weeks of days
    num_nurses = 12

    # ============================================================
    # (A) Overall Schedule Grid
    # For overall day d (from start_date) and nurse n,
    # the assignment is given by:
    #      master_pattern[(d - n*7) mod 84]
    overall_schedule = np.empty((horizon, num_nurses), dtype=object)
    overall_dates = [start_date + timedelta(days=d) for d in range(horizon)]
    for d in range(horizon):
        for n in range(num_nurses):
            idx = (d - n * days_per_week) % horizon
            overall_schedule[d, n] = master_pattern[idx]

    # ============================================================
    # (B) Personal Schedule View
    # For a selected nurse, we show the nurse’s 84‑day (personal) schedule
    # arranged as a calendar: rows = week (Week 1, Week 2, …), columns = day names.
    #
    # Note: A nurse’s personal schedule starts on (start_date + n*7).
    #
    # ============================================================
    st.markdown("---")
    view_option = st.radio("Select Schedule View", ("Overall Schedule Grid", "Personal Schedule View"))

    if view_option == "Overall Schedule Grid":
        st.subheader("Overall Schedule Grid")
        date_labels = [dt.strftime("%b %d (%a)") for dt in overall_dates]
        df_overall = pd.DataFrame(overall_schedule, index=date_labels, columns=valid_names)
        st.dataframe(df_overall.style.set_properties(**{"text-align": "center"}))
        st.markdown(
            """
**Legend:**
- **D:** Day shift (12 hours)
- **N:** Night shift (12 hours)
- **Blank:** Off day
            """
        )
    else:
        st.subheader("Personal Schedule View")
        selected_nurse = st.selectbox("Select Nurse", valid_names)
        nurse_index = valid_names.index(selected_nurse)
        # Nurse n's personal schedule covers 84 days starting on:
        nurse_start = start_date + timedelta(days=nurse_index * days_per_week)
        nurse_dates = [nurse_start + timedelta(days=d) for d in range(horizon)]
        nurse_schedule = []
        for d in range(horizon):
            idx = (d - nurse_index * days_per_week) % horizon
            nurse_schedule.append(master_pattern[idx])
        # Create a DataFrame with Date and Shift.
        df_nurse = pd.DataFrame({
            "Date": nurse_dates,
            "Shift": nurse_schedule
        })
        # Convert the Date column to datetime (if not already)
        df_nurse["Date"] = pd.to_datetime(df_nurse["Date"])

        # For the calendar view, we group by the Monday of each week.
        df_nurse["Week Start"] = df_nurse["Date"].apply(lambda d: d - timedelta(days=d.weekday()))
        df_nurse["Weekday"] = df_nurse["Date"].dt.day_name()
        pivot = df_nurse.pivot(index="Week Start", columns="Weekday", values="Shift")
        # Order the columns as Monday, Tuesday, …, Sunday.
        weekday_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        pivot = pivot.reindex(columns=weekday_order)
        # Rename the index to Week numbers.
        pivot.index = [f"Week {i+1}" for i in range(len(pivot))]
        st.dataframe(pivot.style.set_properties(**{"text-align": "center"}))
        st.markdown(
            """
**Legend:**
- **D:** Day shift (12 hours)
- **N:** Night shift (12 hours)
- **Blank:** Off day
            """
        )