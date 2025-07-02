class QualityMonitor:
    def __init__(self):
        self.issues = []

    def check_completeness(self, records, required_fields):
        for record in records:
            for field in required_fields:
                if field not in record or record[field] is None:
                    self.issues.append((record, f'Missing field: {field}'))

    def check_outliers(self, records, field, min_val, max_val):
        for record in records:
            value = record.get(field)
            if value is not None and (value < min_val or value > max_val):
                self.issues.append((record, f'Outlier in {field}: {value}'))

    def report(self):
        return self.issues 