# core/ai/public_apis.py
# Curated free public APIs the engine can recommend and integrate
# when generating apps that need external data sources.
# Source: https://github.com/public-apis/public-apis

PUBLIC_APIS = {
    "weather": {
        "name": "Open-Meteo",
        "url": "https://api.open-meteo.com/v1/forecast",
        "docs": "https://open-meteo.com/en/docs",
        "auth": "none",
        "description": "Free weather forecasts — no API key needed",
        "example": "https://api.open-meteo.com/v1/forecast?latitude=52.52&longitude=13.41&current_weather=true"
    },
    "maps": {
        "name": "Nominatim (OpenStreetMap)",
        "url": "https://nominatim.openstreetmap.org",
        "docs": "https://nominatim.org/release-docs/latest/api/Overview/",
        "auth": "none",
        "description": "Free geocoding and reverse geocoding — no API key needed",
        "example": "https://nominatim.openstreetmap.org/search?q=London&format=json"
    },
    "currency": {
        "name": "Frankfurter",
        "url": "https://api.frankfurter.app",
        "docs": "https://www.frankfurter.app/docs",
        "auth": "none",
        "description": "Free currency exchange rates — no API key needed",
        "example": "https://api.frankfurter.app/latest?from=USD&to=EUR"
    },
    "news": {
        "name": "NewsData.io",
        "url": "https://newsdata.io/api/1/news",
        "docs": "https://newsdata.io/documentation",
        "auth": "apikey",
        "description": "Free tier: 200 requests/day. Get key at newsdata.io",
        "example": "https://newsdata.io/api/1/news?apikey=YOUR_KEY&language=en"
    },
    "stocks": {
        "name": "Alpha Vantage",
        "url": "https://www.alphavantage.co/query",
        "docs": "https://www.alphavantage.co/documentation/",
        "auth": "apikey",
        "description": "Free tier: 25 requests/day. Get key at alphavantage.co",
        "example": "https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol=IBM&apikey=YOUR_KEY"
    },
    "crypto": {
        "name": "CoinGecko",
        "url": "https://api.coingecko.com/api/v3",
        "docs": "https://www.coingecko.com/en/api/documentation",
        "auth": "none",
        "description": "Free crypto prices — no API key needed",
        "example": "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd"
    },
    "jokes": {
        "name": "JokeAPI",
        "url": "https://v2.jokeapi.dev/joke",
        "docs": "https://jokeapi.dev/",
        "auth": "none",
        "description": "Free jokes API — no API key needed",
        "example": "https://v2.jokeapi.dev/joke/Any"
    },
    "quotes": {
        "name": "Quotable",
        "url": "https://api.quotable.io",
        "docs": "https://github.com/lukePeavey/quotable",
        "auth": "none",
        "description": "Free random quotes — no API key needed",
        "example": "https://api.quotable.io/random"
    },
    "images": {
        "name": "Unsplash",
        "url": "https://api.unsplash.com",
        "docs": "https://unsplash.com/documentation",
        "auth": "apikey",
        "description": "Free tier: 50 requests/hour. Get key at unsplash.com/developers",
        "example": "https://api.unsplash.com/photos/random?client_id=YOUR_KEY"
    },
    "food": {
        "name": "TheMealDB",
        "url": "https://www.themealdb.com/api/json/v1/1",
        "docs": "https://www.themealdb.com/api.php",
        "auth": "none",
        "description": "Free meal/recipe database — no API key needed",
        "example": "https://www.themealdb.com/api/json/v1/1/random.php"
    },
    "movies": {
        "name": "TMDB",
        "url": "https://api.themoviedb.org/3",
        "docs": "https://developer.themoviedb.org/docs",
        "auth": "apikey",
        "description": "Free movie/TV database. Get key at themoviedb.org",
        "example": "https://api.themoviedb.org/3/movie/popular?api_key=YOUR_KEY"
    },
    "books": {
        "name": "Open Library",
        "url": "https://openlibrary.org/api",
        "docs": "https://openlibrary.org/developers/api",
        "auth": "none",
        "description": "Free book database — no API key needed",
        "example": "https://openlibrary.org/search.json?q=the+lord+of+the+rings"
    },
    "github": {
        "name": "GitHub API",
        "url": "https://api.github.com",
        "docs": "https://docs.github.com/en/rest",
        "auth": "optional",
        "description": "Free: 60 req/hr unauthenticated, 5000 with token",
        "example": "https://api.github.com/users/octocat"
    },
    "ip": {
        "name": "ipapi",
        "url": "https://ipapi.co",
        "docs": "https://ipapi.co/api/",
        "auth": "none",
        "description": "Free IP geolocation — no API key needed",
        "example": "https://ipapi.co/json/"
    },
    "translate": {
        "name": "LibreTranslate",
        "url": "https://libretranslate.com/translate",
        "docs": "https://libretranslate.com/docs",
        "auth": "optional",
        "description": "Free open-source translation API",
        "example": "POST https://libretranslate.com/translate with {q, source, target}"
    },
    "qr": {
        "name": "QR Code Generator",
        "url": "https://api.qrserver.com/v1/create-qr-code",
        "docs": "https://goqr.me/api/",
        "auth": "none",
        "description": "Free QR code generation — no API key needed",
        "example": "https://api.qrserver.com/v1/create-qr-code/?size=150x150&data=Example"
    },
    "email_validation": {
        "name": "Abstract Email Validation",
        "url": "https://emailvalidation.abstractapi.com/v1",
        "docs": "https://www.abstractapi.com/api/email-verification-validation-api",
        "auth": "apikey",
        "description": "Free tier: 100 req/month. Get key at abstractapi.com",
        "example": "https://emailvalidation.abstractapi.com/v1/?api_key=YOUR_KEY&email=example@example.com"
    },
    "sports": {
        "name": "TheSportsDB",
        "url": "https://www.thesportsdb.com/api/v1/json/3",
        "docs": "https://www.thesportsdb.com/api.php",
        "auth": "none",
        "description": "Free sports data — no API key needed",
        "example": "https://www.thesportsdb.com/api/v1/json/3/all_leagues.php"
    },
    "nasa": {
        "name": "NASA APIs",
        "url": "https://api.nasa.gov",
        "docs": "https://api.nasa.gov/",
        "auth": "apikey",
        "description": "Free NASA data including APOD. Get key at api.nasa.gov",
        "example": "https://api.nasa.gov/planetary/apod?api_key=DEMO_KEY"
    },
    "dictionary": {
        "name": "Free Dictionary API",
        "url": "https://api.dictionaryapi.dev/api/v2/entries/en",
        "docs": "https://dictionaryapi.dev/",
        "auth": "none",
        "description": "Free dictionary — no API key needed",
        "example": "https://api.dictionaryapi.dev/api/v2/entries/en/hello"
    }
}

# Keywords that map to API categories
API_KEYWORDS = {
    "weather": ["weather", "forecast", "temperature", "climate", "rain", "wind"],
    "maps": ["map", "location", "geocod", "address", "coordinates", "latitude", "longitude"],
    "currency": ["currency", "exchange rate", "forex", "convert money", "USD", "EUR"],
    "news": ["news", "articles", "headlines", "blog", "feed"],
    "stocks": ["stock", "shares", "market", "trading", "portfolio", "investment", "finance"],
    "crypto": ["crypto", "bitcoin", "ethereum", "blockchain", "coin", "token"],
    "food": ["recipe", "meal", "food", "cooking", "ingredient", "cuisine"],
    "movies": ["movie", "film", "cinema", "TV show", "series", "entertainment"],
    "books": ["book", "library", "reading", "author", "isbn"],
    "github": ["github", "repository", "code", "developer profile", "commits"],
    "images": ["image", "photo", "picture", "gallery", "unsplash"],
    "translate": ["translat", "language", "multilingual"],
    "qr": ["qr code", "barcode", "scan"],
    "sports": ["sport", "football", "basketball", "soccer", "league", "team score"],
    "nasa": ["nasa", "space", "astronomy", "planet", "satellite"],
    "dictionary": ["dictionary", "definition", "word meaning", "vocabulary"],
}


def detect_needed_apis(request: str) -> list:
    """Detect which public APIs would be useful for a given project request."""
    request_lower = request.lower()
    needed = []
    for category, keywords in API_KEYWORDS.items():
        if any(kw in request_lower for kw in keywords):
            needed.append(PUBLIC_APIS[category])
    return needed


def get_api_hint(request: str) -> str:
    """Return a hint string for the pipeline about available public APIs."""
    apis = detect_needed_apis(request)
    if not apis:
        return ""
    lines = ["\nAVAILABLE FREE PUBLIC APIS FOR THIS PROJECT:"]
    for api in apis:
        auth_note = "NO API KEY NEEDED" if api["auth"] == "none" else f"Free API key needed: {api['docs']}"
        lines.append(f"- {api['name']}: {api['description']} ({auth_note})")
        lines.append(f"  Base URL: {api['url']}")
        lines.append(f"  Example: {api['example']}")
    lines.append("\nUse these APIs directly in the generated code where relevant.")
    return "\n".join(lines)
