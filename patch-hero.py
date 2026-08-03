import re

file_path = 'js/ui.js'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace(
    "const { totalMustAttend, totalSafeSkips, forecastOverallAttendance } = overallStats;",
    "const { totalMustAttend, totalSafeSkips, forecastOverallAttendance, totalClasses, totalSubjects } = overallStats;"
)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
