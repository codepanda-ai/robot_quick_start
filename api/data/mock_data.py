from interfaces.models import Activity, Buddy, WeatherForecast, Budget, Vibe


MOCK_ACTIVITIES: list[Activity] = [
    Activity(
        id="sg_1", name="MacLehose Trail Stage 2", type="hiking",
        budget=Budget.LOW, vibe=Vibe.CHILL,
        reason="Scenic coastal views, moderate difficulty, perfect for a relaxed Saturday.",
    ),
    Activity(
        id="sg_2", name="Lan Kwai Fong Pub Crawl", type="nightlife",
        budget=Budget.HIGH, vibe=Vibe.SOCIAL,
        reason="Great for meeting people, lively atmosphere, tons of bar options.",
    ),
    Activity(
        id="sg_3", name="Dim Sum at Tim Ho Wan", type="dining",
        budget=Budget.LOW, vibe=Vibe.CHILL,
        reason="Michelin-starred dim sum on a budget. Perfect casual weekend brunch.",
    ),
    Activity(
        id="sg_4", name="Shek O Beach Day", type="beach",
        budget=Budget.LOW, vibe=Vibe.CHILL,
        reason="Quiet beach with great Thai food nearby. Ideal for unwinding.",
    ),
    Activity(
        id="sg_5", name="Board Game Cafe", type="indoor",
        budget=Budget.MEDIUM, vibe=Vibe.SOCIAL,
        reason="Rain-proof option, fun with friends, great coffee and snacks.",
    ),
    Activity(
        id="sg_6", name="Peak Circle Walk", type="hiking",
        budget=Budget.LOW, vibe=Vibe.ADVENTUROUS,
        reason="Iconic skyline views, moderate challenge, rewarding panoramas.",
    ),
]


MOCK_BUDDIES: list[Buddy] = [
    Buddy(id="b_1", name="Alice Chen", open_id="ou_mock_alice", interests=["hiking", "beach"]),
    Buddy(id="b_2", name="Bob Wong", open_id="ou_mock_bob", interests=["dining", "nightlife"]),
    Buddy(id="b_3", name="Carol Lee", open_id="ou_mock_carol", interests=["hiking", "indoor"]),
    Buddy(id="b_4", name="Dave Liu", open_id="ou_mock_dave", interests=["beach", "dining", "nightlife"]),
]


MOCK_WEATHER: list[WeatherForecast] = [
    WeatherForecast(day="Saturday", temp=26, condition="Sunny", humidity=65),
    WeatherForecast(day="Sunday", temp=23, condition="Partly Cloudy", humidity=72),
]
