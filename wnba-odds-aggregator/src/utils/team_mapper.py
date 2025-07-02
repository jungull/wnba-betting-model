class TeamMapper:
    def __init__(self, mapping=None):
        # Example mapping; in production, load from DB or config
        self.mapping = mapping or {
            'Las Vegas Aces': 'Las Vegas Aces',
            'LV Aces': 'Las Vegas Aces',
            'New York Liberty': 'New York Liberty',
            'NY Liberty': 'New York Liberty',
            # Add more mappings as needed
        }

    def standardize(self, name):
        return self.mapping.get(name, name) 