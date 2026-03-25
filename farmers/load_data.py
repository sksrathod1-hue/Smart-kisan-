import csv
from .models import Scheme

def get_rules(department):
    """
    Auto assign rules based on department
    """
    department = department.lower()

    if "agriculture" in department:
        return 18, 60, 500000, "All"

    elif "banking" in department:
        return 21, 65, 1000000, "All"

    elif "irrigation" in department:
        return 18, 65, 800000, "All"

    elif "fisheries" in department:
        return 18, 60, 600000, "All"

    elif "dairy" in department:
        return 18, 65, 700000, "All"

    elif "horticulture" in department:
        return 18, 60, 500000, "All"

    elif "energy" in department:
        return 21, 65, 1000000, "All"

    else:
        return 18, 65, 1000000, "All"


def load_schemes():
    with open('data/farmer_schemes_dataset.csv', newline='', encoding='utf-8') as file:
        reader = csv.DictReader(file)

        for row in reader:
            min_age, max_age, income_limit, category = get_rules(row['department'])

            Scheme.objects.create(
                scheme_name=row['scheme_name'],
                scheme_type=row['scheme_type'],
                state=row['state'],
                department=row['department'],
                min_age=min_age,
                max_age=max_age,
                income_limit=income_limit,
                category=category
            )

    print("Smart AI Data Imported Successfully!")