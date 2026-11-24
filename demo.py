"""Sample immersion journals for the in-app demo."""

from datetime import timedelta
from urllib.parse import quote


JOURNALS = (
    {
        "language": "Spanish",
        "videos": ("Una mañana en el mercado", "Cocinar con mi abuela", "Por las calles de Madrid"),
        "articles": ("Mercado", "Tortilla de patatas", "Madrid", "Ferrocarril", "Olivo"),
        "wiki": "es",
        "cards": (
            ("¿Cuánto cuesta un kilo?", "How much does a kilo cost?", "Mercado"),
            ("Le damos la vuelta a la tortilla.", "We flip the omelette over.", "Tortilla de patatas"),
            ("El tren sale a las ocho.", "The train leaves at eight.", "Ferrocarril"),
            ("Cruzamos la plaza a pie.", "We cross the square on foot.", "Madrid"),
        ),
        "days_ago": (0, 1, 2, 3, 4, 5, 6, 9, 10, 13, 15, 18, 19, 23, 26, 29, 38, 46, 56, 72, 89, 106),
    },
    {
        "language": "Japanese",
        "videos": ("朝ごはんを作ろう", "京都の町を歩く", "駅で切符を買う"),
        "articles": ("喫茶店", "おにぎり", "京都市", "鉄道", "茶"),
        "wiki": "ja",
        "cards": (
            ("朝ごはんを作ります。", "I make breakfast.", "おにぎり"),
            ("駅はどこですか。", "Where is the station?", "鉄道"),
            ("お茶をください。", "Tea, please.", "茶"),
            ("喫茶店で本を読みます。", "I read a book at the coffee shop.", "喫茶店"),
        ),
        "days_ago": (0, 1, 3, 4, 5, 6, 7, 11, 14, 19, 25, 28, 34, 45, 63, 81),
    },
)


def populate(db, today):
    """Create both journals atomically and return the first demo language ID."""
    db.execute("BEGIN IMMEDIATE")
    existing = db.execute("SELECT language_id FROM demo_journals ORDER BY language_id").fetchone()
    if existing:
        return existing[0]

    first_id = None
    for journal in JOURNALS:
        name = base_name = journal["language"] + " (demo)"
        suffix = 2
        while db.execute("SELECT 1 FROM languages WHERE name=?", (name,)).fetchone():
            name = f"{base_name} {suffix}"
            suffix += 1
        language_id = db.execute("INSERT INTO languages(name) VALUES (?)", (name,)).lastrowid
        db.execute("INSERT INTO demo_journals(language_id) VALUES (?)", (language_id,))
        if first_id is None:
            first_id = language_id

        wiki = f"https://{journal['wiki']}.wikipedia.org/wiki/"
        activities = []
        video_count = 0
        for index, offset in enumerate(reversed(journal["days_ago"])):
            day = (today - timedelta(days=offset)).isoformat()
            if index % 3 != 1:
                series = journal["videos"][video_count % len(journal["videos"])]
                title = f"{series} · {video_count // len(journal['videos']) + 1}"
                video_count += 1
                activities.append((language_id, "video", title, day, 12 + index * 7 % 45, None))
            if index % 3 != 0:
                topic = journal["articles"][index % len(journal["articles"])]
                url = wiki + quote(topic.replace(" ", "_"))
                activities.append((language_id, "article", topic, day, 6 + index * 5 % 22, url))
        db.executemany("""INSERT INTO activities(language_id, kind, title, day, minutes, url)
                          VALUES (?, ?, ?, ?, ?, ?)""", activities)
        db.executemany("INSERT INTO cards(language_id, front, back, url) VALUES (?, ?, ?, ?)",
                       [(language_id, front, back, wiki + quote(topic.replace(" ", "_")))
                        for front, back, topic in journal["cards"]])
    return first_id
