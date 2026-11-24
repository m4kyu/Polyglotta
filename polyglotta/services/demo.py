"""Sample immersion journals for the in-app demo."""

from datetime import date, timedelta
from urllib.parse import quote


from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Activity, Card, DemoJournal, Language


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


def populate(db: Session, today: date, account_id: int):
    """Create both journals atomically and return the first demo language ID."""
    existing = db.scalar(select(DemoJournal.language_id).join(Language).where(Language.account_id == account_id).order_by(DemoJournal.language_id).limit(1))
    if existing is not None:
        return existing

    first_id = None
    for journal in JOURNALS:
        name = base_name = journal["language"] + " (demo)"
        suffix = 2
        while db.scalar(select(Language.id).where(Language.account_id == account_id, Language.name == name)) is not None:
            name = f"{base_name} {suffix}"
            suffix += 1
        language = Language(name=name, account_id=account_id)
        db.add(language)
        db.flush()
        language_id = language.id
        db.add(DemoJournal(language_id=language_id))
        if first_id is None:
            first_id = language_id

        wiki = f"https://{journal['wiki']}.wikipedia.org/wiki/"
        video_count = 0
        for index, offset in enumerate(reversed(journal["days_ago"])):
            day = (today - timedelta(days=offset)).isoformat()
            if index % 3 != 1:
                series = journal["videos"][video_count % len(journal["videos"])]
                title = f"{series} · {video_count // len(journal['videos']) + 1}"
                video_count += 1
                db.add(Activity(language_id=language_id, kind="video", title=title,
                                day=day, minutes=12 + index * 7 % 45))
            if index % 3 != 0:
                topic = journal["articles"][index % len(journal["articles"])]
                url = wiki + quote(topic.replace(" ", "_"))
                db.add(Activity(language_id=language_id, kind="article", title=topic,
                                day=day, minutes=6 + index * 5 % 22, url=url))
        for front, back, topic in journal["cards"]:
            db.add(Card(language_id=language_id, front=front, back=back,
                        url=wiki + quote(topic.replace(" ", "_"))))
    return first_id
