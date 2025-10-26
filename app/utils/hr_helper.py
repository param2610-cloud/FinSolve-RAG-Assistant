"""
hr helper - load and query hr data
from notebook rag.ipynb
"""
import pandas as pd
import os
from typing import Tuple, Dict

# load hr data at initialization
HR_DATA = None
hr_csv_path = "resources/data/hr/hr_data.csv"
if os.path.exists(hr_csv_path):
    HR_DATA = pd.read_csv(hr_csv_path)
    print(f"✅ Loaded HR data: {len(HR_DATA)} records")
else:
    print(f"⚠️ HR data file not found at {hr_csv_path}")
    HR_DATA = None


def query_hr_data(question: str, user_role: str, processed_query: Dict) -> Tuple[str, pd.DataFrame]:
    """handle hr-specific queries using spacy-processed information - from notebook"""
    from app.services.users import ROLE_PERMISSIONS
    
    if "hr" not in ROLE_PERMISSIONS.get(user_role, []):
        return "❌ Access Denied: You don't have permission to access HR data.", None
    
    if HR_DATA is None:
        return "❌ HR data not found.", None
    
    # use processed query information
    entities = processed_query["entities"]
    intent = processed_query["intent"]
    query_lower = processed_query["clean_query"].lower()
    
    try:
        result_df = None
        
        # search by employee name (using spacy entity extraction)
        if entities["persons"]:
            person_name = entities["persons"][0]
            result_df = HR_DATA[HR_DATA['full_name'].str.contains(person_name, case=False, na=False)]
            if not result_df.empty:
                return f"✅ Found employee: {person_name}", result_df
        
        # salary queries with aggregation detection
        if "salary" in query_lower or "payroll" in query_lower or "compensation" in query_lower:
            if intent["is_aggregation"]:
                # calculate statistics
                stats = {
                    'Average Salary': [f"₹{HR_DATA['salary'].mean():,.2f}"],
                    'Median Salary': [f"₹{HR_DATA['salary'].median():,.2f}"],
                    'Min Salary': [f"₹{HR_DATA['salary'].min():,.2f}"],
                    'Max Salary': [f"₹{HR_DATA['salary'].max():,.2f}"],
                    'Total Employees': [len(HR_DATA)]
                }
                result_df = pd.DataFrame(stats)
            elif "highest" in query_lower or "top" in query_lower:
                # extract number if specified
                top_n = 10
                if entities["numbers"]:
                    try:
                        top_n = int(entities["numbers"][0])
                    except:
                        pass
                result_df = HR_DATA.nlargest(top_n, 'salary')[['employee_id', 'full_name', 'role', 'department', 'salary']]
            elif "lowest" in query_lower or "bottom" in query_lower:
                result_df = HR_DATA.nsmallest(10, 'salary')[['employee_id', 'full_name', 'role', 'department', 'salary']]
            else:
                result_df = HR_DATA[['employee_id', 'full_name', 'role', 'department', 'salary']]
        
        if result_df is not None and not result_df.empty:
            return "✅ HR Data Retrieved", result_df.head(20)
        
        return "⚠️ No matching HR data found", None
        
    except Exception as e:
        return f"❌ Error processing HR query: {str(e)}", None


def query_hr_departments(query_lower: str, intent: Dict) -> pd.DataFrame:
    """handle department-specific hr queries - from notebook"""
    if intent["is_aggregation"]:
        dept_stats = HR_DATA.groupby('department').agg({
            'employee_id': 'count',
            'salary': ['mean', 'sum'],
            'performance_rating': 'mean'
        }).round(2)
        dept_stats.columns = ['Employee Count', 'Avg Salary', 'Total Salary', 'Avg Performance']
        return dept_stats.reset_index()
    else:
        return HR_DATA[['employee_id', 'full_name', 'department', 'role']]


def query_hr_performance(query_lower: str) -> pd.DataFrame:
    """handle performance-related hr queries - from notebook"""
    if "top" in query_lower or "highest" in query_lower:
        return HR_DATA.nlargest(10, 'performance_rating')[['employee_id', 'full_name', 'department', 'performance_rating', 'last_review_date']]
    else:
        return HR_DATA[['employee_id', 'full_name', 'department', 'performance_rating', 'last_review_date']].sort_values('performance_rating', ascending=False)


def query_hr_attendance(query_lower: str, intent: Dict) -> pd.DataFrame:
    """handle leave and attendance queries - from notebook"""
    if intent["is_aggregation"]:
        avg_stats = {
            'Avg Leave Balance': [HR_DATA['leave_balance'].mean()],
            'Avg Leaves Taken': [HR_DATA['leaves_taken'].mean()],
            'Avg Attendance %': [f"{HR_DATA['attendance_pct'].mean():.2f}%"]
        }
        return pd.DataFrame(avg_stats)
    else:
        return HR_DATA[['employee_id', 'full_name', 'leave_balance', 'leaves_taken', 'attendance_pct']]


def query_hr_data_extended(question: str, user_role: str, processed_query: Dict) -> Tuple[str, pd.DataFrame]:
    """extended hr query handler with all query types - from notebook"""
    
    status, result_df = query_hr_data(question, user_role, processed_query)
    
    # if already found result, return it
    if result_df is not None:
        return status, result_df
    
    # otherwise check other query types
    query_lower = processed_query["clean_query"].lower()
    intent = processed_query["intent"]
    
    try:
        # department queries
        if "department" in query_lower:
            return "✅ HR Data Retrieved", query_hr_departments(query_lower, intent)
        
        # performance queries
        elif "performance" in query_lower or "rating" in query_lower:
            return "✅ HR Data Retrieved", query_hr_performance(query_lower)
        
        # leave/attendance queries
        elif "leave" in query_lower or "attendance" in query_lower:
            return "✅ HR Data Retrieved", query_hr_attendance(query_lower, intent)
        
        # default summary
        else:
            summary = {
                'Total Employees': [len(HR_DATA)],
                'Average Salary': [f"₹{HR_DATA['salary'].mean():,.2f}"],
                'Departments': [HR_DATA['department'].nunique()],
                'Avg Performance': [f"{HR_DATA['performance_rating'].mean():.2f}"],
                'Avg Attendance': [f"{HR_DATA['attendance_pct'].mean():.2f}%"]
            }
            return "✅ HR Summary", pd.DataFrame(summary)
    
    except Exception as e:
        return f"❌ Error: {str(e)}", None
