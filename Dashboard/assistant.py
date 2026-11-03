"""Turn what you said into one dashboard action.

Common commands ("pause", "next", "volume 30", "show stocks") are matched by rules, so they're instant and work with
AI off. Anything else goes to the AI (local Ollama or an API through llm.py), which answers with a JSON action."""

import re

from llm import LLMError
from widgets import timers

TILES = {"photos": "photos", "photo": "photos", "pictures": "photos", "slideshow": "photos",
         "music": "music", "youtube": "music", "player": "music", "song": "music",
         "stocks": "stocks", "stock": "stocks", "market": "stocks", "markets": "stocks",
         "cyber": "cyber", "security": "cyber", "attacks": "cyber",
         "news": "news", "headlines": "news",
         "pc": "pc", "system": "pc", "laptop": "pc",
         "calendar": "calendar", "schedule": "calendar", "agenda": "calendar",
         "timers": "timers", "timer": "timers", "reminders": "timers",
         "tasks": "tasks", "task": "tasks", "todos": "tasks", "todo": "tasks",
         "whatsapp": "whatsapp", "messages": "whatsapp"}

SYSTEM = """You control a voice-operated dashboard on a small second monitor. Reply with ONE JSON object, nothing else.

Actions (pick exactly one):
{"action": "play_song", "query": "<what to search on YouTube>"}
{"action": "pause"} | {"action": "resume"} | {"action": "next"} | {"action": "previous"}
{"action": "volume", "level": <0-100>}   (relative requests: current volume is given below)
{"action": "maximize", "tile": "photos|music|stocks|cyber|news|pc|calendar|timers|tasks|weather|whatsapp"}
{"action": "restore"}                       (back to the normal grid)
{"action": "stock_quote", "symbol": "<Yahoo ticker, e.g. AAPL, ^GSPC, ^NSEI, RELIANCE.NS, BTC-USD>"}
{"action": "market_summary"}               (how the watchlist is doing)
{"action": "add_stock", "symbol": "<Yahoo ticker>"} | {"action": "remove_stock", "symbol": "<Yahoo ticker>"}
{"action": "cyber_brief"}                  (summarise the latest cyber attacks / security news)
{"action": "explain_story", "kind": "cyber|news", "index": <1-based position in that list>} or {"action": "explain_story", "kind": "cyber|news", "query": "<words from the headline>"}
{"action": "news_brief"}                   (top general news headlines)
{"action": "timer", "seconds": <number>, "label": "<what it's for>"}
{"action": "reminder", "time": "<HH:MM 24-hour>", "label": "<what to remind>"} or {"action": "reminder", "seconds": <from now>, "label": "..."}
{"action": "timer_cancel", "label": "<words from its label, optional>"} | {"action": "timer_list"}
{"action": "timer_ack"} | {"action": "timer_snooze", "minutes": <number>}   (stop / snooze a ringing timer or reminder)
{"action": "task_add", "text": "<the task; keep a due date if said, e.g. 'pay the bill by friday 6 pm'>"} | {"action": "task_list"} | {"action": "task_done", "ref": "<words from the task, or its number in the list>"}   (the to-do / task list with how long each task has been pending)
{"action": "agenda", "day": "today|tomorrow"} | {"action": "next_event"}   (calendar)
{"action": "pc_status"}                    (CPU, GPU, memory, disk of this PC)
{"action": "pc_agent", "text": "<the request, as said>"}   (PC care by System Utilities: clean up junk, free disk space, duplicates, organise folders / downloads, drivers, memory / RAM, speed up a slow PC, startup apps, processes, suspicious programs)
{"action": "briefing"}                     (morning briefing: weather, calendar, markets, messages, news)
{"action": "edit_layout"}                  (rearrange / resize / add / remove widgets)
{"action": "create_widget", "request": "<what the new widget should show / do>"}   (build a NEW custom widget)
{"action": "edit_widget", "name": "<widget name>", "request": "<the change>"}   (change a custom widget)
{"action": "read_widget", "name": "<widget name>"} | {"action": "show_widget", "name": "<widget name>"}   (custom widgets)
{"action": "weather"}                      (current conditions and today's forecast)
{"action": "show_weather"}                 (open the full weather view)
{"action": "read_whatsapp"}                (read out unread WhatsApp chats)
{"action": "mute_replies"} | {"action": "unmute_replies"}   (stop / start speaking answers aloud)
{"action": "next_photo"} | {"action": "previous_photo"}
{"action": "open_whatsapp"} | {"action": "close_whatsapp"}
{"action": "show_dashboard"} | {"action": "hide_dashboard"}   (the whole dashboard window)
{"action": "answer", "text": "<short spoken answer, 1-3 sentences>"}   (general questions, chit-chat)

The request came from speech-to-text, so allow for misheard words. Use "answer" when nothing else fits.
Never answer questions about this PC's processes, programs, files, storage, memory, drivers or startup yourself:
use pc_agent, which actually checks the PC."""


def _num(word):
    words = {"zero": 0, "ten": 10, "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60,
             "seventy": 70, "eighty": 80, "ninety": 90, "hundred": 100, "max": 100, "full": 100}
    return int(word) if word.isdigit() else words.get(word)


def quick(text, state):
    """Rule-based match for everyday commands; None when the AI is needed."""
    t = re.sub(r"[^\w\s^.-]", "", text.lower().replace("'s", " is")).strip()
    t = re.sub(r"^(hey |ok |okay )?(jarvis|dashboard|computer)[, ]*", "", t).strip()
    t = re.sub(r"\b(please|can you|could you|now)\b", "", t).strip()
    t = re.sub(r"\s+", " ", t)
    if not t:
        return None
    if state.get("alarm"):                   # a timer is ringing: short replies are about the alarm
        m = re.fullmatch(r"snooze( it| the alarm| the timer)?( for)?( (\w+) minutes?)?", t)
        if m:
            return {"action": "timer_snooze", "minutes": timers._num(m.group(4)) if m.group(4) else 5}
        if re.fullmatch(r"(stop|ok|okay|dismiss|done|got it|thanks|thank you|acknowledged?|shut up|quiet|enough|"
                        r"turn (it )?off|stop (it|the (alarm|timer|bell|reminder|ringing))|i am up|cancel( it)?)", t):
            return {"action": "timer_ack"}
    original = re.sub(r"^(hey |ok |okay )?(jarvis|dashboard|computer)[, ]*", "", text.strip(), flags=re.I)
    # Widget Studio: matched on the original text so the request keeps its wording
    m = re.match(r"(?:please )?(?:create|make|build|design|add)(?: me)?(?: a| an)?(?: new)? (?:custom )?widget"
                 r"(?:\s+(?:that|which|for|to|showing|with|of))?\s*[:,]?\s*(.+)$", original, re.I)
    if m:
        return {"action": "create_widget", "request": m.group(1).strip()}
    m = re.match(r"(?:change|edit|update|modify|tweak|fix)(?: the| my)? (.+?) widget(?:\s+(?:to|so|and|so that))?\s*[:,]?\s*(.+)$",
                 original, re.I)
    if m:
        return {"action": "edit_widget", "name": m.group(1).strip(), "request": m.group(2).strip()}
    m = re.fullmatch(r"read(?: me)?(?: out)?(?: the| my)? (.+?) widget", t)
    if m:
        return {"action": "read_widget", "name": m.group(1)}
    m = re.fullmatch(r"(?:show|open|maximi[sz]e)(?: the| my)? (.+?) widget", t)
    if m:
        return {"action": "show_widget", "name": m.group(1)}
    # Task list: matched before the PC-care words below ("add a task to delete old downloads" is a task, not a clean-up).
    # Stripped of a trailing full stop only; the task keeps its wording and capitals.
    said = original.rstrip(" .!?")
    m = re.match(r"(?:please )?(?:add|create|make|new)(?: me)?(?: a| an| the| another)?(?: new)? (?:task|to[ -]?do|todo)"
                 r"(?:\s+(?:to|for|called|named|that|about))?\s*[:,]?\s*(.+)$", said, re.I) or \
        re.match(r"(?:please )?(?:add|put) (.+?) (?:to|on|onto|in) (?:my |the )?(?:task|to[ -]?do|todo)s?(?: list)?$", said, re.I) or \
        re.match(r"(?:please )?(?:remind me to|i need to|i have to) (.+?) (?:as a task|to my (?:task|to[ -]?do) list)$", said, re.I)
    if m:
        return {"action": "task_add", "text": m.group(1).strip()}
    if re.fullmatch(r"what is on( my| the)? (to[ -]?do|task) list|"
                    r"(what|which)( are| is)?( my| the)?( pending| open| outstanding)? (tasks|to[ -]?dos?)( do i have| are pending| are left| left)?|"
                    r"(list|show|read|tell)( me)?( out)?( my| the)?( pending| open| outstanding)? (tasks|to[ -]?do list|to[ -]?dos?|task list)|"
                    r"what do i (have to|need to) do( today)?|how many (pending |open )?tasks( do i have| are pending| are left)?|"
                    r"any (pending |open |overdue )?tasks( left| pending)?|(my )?(task|to[ -]?do) list", t):
        return {"action": "task_list"}
    m = re.match(r"(?:please )?(?:mark|set)(?: the| my)?(?: task)? (.+?) (?:as |to )?(?:done|complete|completed|finished)$", said, re.I) or \
        re.match(r"(?:please )?(?:complete|finish|tick off|check off|cross off)(?: the| my)? task (.+)$", said, re.I) or \
        re.match(r"(?:please )?(?:complete|finish|tick off|check off|cross off) (.+?) (?:from|on|in) (?:my |the )?(?:task|to[ -]?do)s?(?: list)?$", said, re.I) or \
        re.match(r"(?:please )?(?:i )?(?:am |have )?(?:done|finished)(?: with)? (?:the |my )?task (.+)$", said, re.I)
    if m:
        return {"action": "task_done", "ref": m.group(1).strip()}
    timer = timers.parse_command(original)
    if timer:
        return timer
    m = re.fullmatch(r"(?:cancel|stop|delete|remove)(?: the| my)?(?: (.+?))? (?:timer|reminder|alarm)s?", t)
    if m:
        return {"action": "timer_cancel", "label": m.group(1)}
    if re.fullmatch(r"(what|which|any) (timers|reminders)( are)?( running| set)?|(list|show)( my)? (timers|reminders)|"
                    r"how (much|long) (time )?(is )?left( on the timer)?", t):
        return {"action": "timer_list"}
    if re.fullmatch(r"good (morning|afternoon|evening)( jarvis)?|(morning|daily|my) briefing|brief me", t):
        return {"action": "briefing"}
    if re.fullmatch(r"(how is|check) (my |the )?(pc|computer|laptop|system)( doing| status)?|(pc|system) status|"
                    r"(cpu|gpu) (usage|temperature|temp)", t):
        return {"action": "pc_status"}
    if not re.match(r"(play|put on)\b", t) and re.search(
            r"\b(clean( ?up)?|cleaning|junk|temp files|delete|storage|disk space|free (up )?space|duplicates?|"
            r"organi[sz]e|downloads?( folder)?|drivers?|memory|ram|boost|speed (it |my pc |things )?up|slow|"
            r"startup( apps| programs)?|process(es)?|orphan(ed|s)?|suspicious|malware|virus|"
            r"running (apps|programs|applications)|background (apps|programs|processes)|task manager|"
            r"what( is|s) running|system utilit(y|ies))\b", t):
        return {"action": "pc_agent", "text": original}   # System Utilities does the PC care
    m = re.fullmatch(r"what is on( my calendar| my schedule)?( for)? (today|tomorrow)|(my )?(schedule|agenda|calendar)"
                     r"( for)?( today| tomorrow)?|(do i have )?any (meetings|events)( today| tomorrow)?", t)
    if m:
        return {"action": "agenda", "day": "tomorrow" if "tomorrow" in t else "today"}
    if re.fullmatch(r"(what is |when is )?my next (meeting|event|appointment|call)", t):
        return {"action": "next_event"}
    if re.fullmatch(r"(today is |the |top |latest )*(news )?headlines( today)?|what is in the news( today)?|"
                    r"(latest|top) news|news (update|brief|summary)", t):
        return {"action": "news_brief"}
    if re.fullmatch(r"(edit|change|customi[sz]e|rearrange) (the )?(layout|dashboard|widgets)", t):
        return {"action": "edit_layout"}
    if re.fullmatch(r"(mute|silence)( your)? (voice|replies|answers|responses?)|stop talking|stop speaking|"
                    r"(do not|dont) (talk|speak)", t):
        return {"action": "mute_replies"}
    if re.fullmatch(r"unmute( your)?( voice| replies| answers| responses?)?|(start )?(talking|speaking) (again|back)|"
                    r"speak again|talk to me", t):
        return {"action": "unmute_replies"}
    if re.fullmatch(r"(read|show|check)( me)?( my)?( new| unread)? (whatsapp )?(messages|chats)( on whatsapp)?|"
                    r"any (new )?(whatsapp )?messages", t):
        return {"action": "read_whatsapp"}
    if re.fullmatch(r"(what is the |hows the |how is the )?weather( like)?( today| now| outside)?|"
                    r"weather (report|update|forecast)", t):
        return {"action": "weather"}
    if re.fullmatch(r"(show|open|maximi[sz]e)( the)? (weather|forecast)( full ?screen)?", t):
        return {"action": "show_weather"}
    m = re.fullmatch(r"explain( the)? (first|second|third|fourth|fifth|top|1st|2nd|3rd|4th|5th|\d)"
                     r"( news| cyber| security)? (story|article|news|one|headline)", t)
    if m:
        order = {"first": 1, "top": 1, "1st": 1, "second": 2, "2nd": 2, "third": 3, "3rd": 3, "fourth": 4, "4th": 4,
                 "fifth": 5, "5th": 5}
        kind = {" news": "news", " cyber": "cyber", " security": "cyber"}.get(m.group(3) or "")
        return {"action": "explain_story", "index": order.get(m.group(2)) or int(m.group(2)), "kind": kind}
    if re.fullmatch(r"(pause|stop)( the)?( music| song| playback)?|be quiet|shut up|mute", t):
        return {"action": "pause"}
    if re.fullmatch(r"(resume|continue|unpause|play)( the)?( music| song)?", t):
        return {"action": "resume"}
    if re.fullmatch(r"(next|skip)( song| track| one)?|skip (this|it)", t):
        return {"action": "next"}
    if re.fullmatch(r"(previous|last|go back to the last)( song| track)", t):
        return {"action": "previous"}
    m = re.fullmatch(r"(?:set )?(?:the )?volume (?:to )?(\w+)(?: percent)?", t)
    if m and _num(m.group(1)) is not None:
        return {"action": "volume", "level": max(0, min(100, _num(m.group(1))))}
    if re.fullmatch(r"(turn (it )?up|louder|volume up)", t):
        return {"action": "volume", "level": min(100, state.get("volume", 60) + 15)}
    if re.fullmatch(r"(turn (it )?down|quieter|softer|volume down)", t):
        return {"action": "volume", "level": max(0, state.get("volume", 60) - 15)}
    if re.fullmatch(r"(next|another) (photo|picture|image)", t):
        return {"action": "next_photo"}
    if re.fullmatch(r"previous (photo|picture|image)", t):
        return {"action": "previous_photo"}
    if re.fullmatch(r"(go back|back|restore|minimi[sz]e|exit full ?screen|close( it| this)?|home|show everything)", t):
        return {"action": "restore"}
    if re.fullmatch(r"(open|show|bring back)( the| my)? dashboard", t):
        return {"action": "show_dashboard"}
    if re.fullmatch(r"(hide|close|minimi[sz]e)( the)? dashboard", t):
        return {"action": "hide_dashboard"}
    if re.fullmatch(r"(open|show)( my)? (whatsapp|messages)", t):
        return {"action": "open_whatsapp"}
    if re.fullmatch(r"(close|hide) (whatsapp|messages)", t):
        return {"action": "close_whatsapp"}
    m = re.fullmatch(r"(?:maximi[sz]e|expand|full ?screen|show|open|zoom)(?: the| my)? (\w+)(?: tile| full ?screen| big)?", t)
    if m and m.group(1) in TILES:
        tile = TILES[m.group(1)]
        return {"action": "open_whatsapp"} if tile == "whatsapp" else {"action": "maximize", "tile": tile}
    if re.search(r"(cyber|security|hack|ransomware|breach)\w* (news|attacks?|update|report|brief)", t):
        return {"action": "cyber_brief"}
    if re.fullmatch(r"(how is the (stock )?markets?( doing)?( today)?|markets? (summary|update)|how are (my )?stocks( doing)?)", t):
        return {"action": "market_summary"}
    m = re.fullmatch(r"(?:play|put on)(?: me)? (.+?)(?: on youtube)?", t)
    if m and m.group(1) not in ("music", "song", "something"):
        return {"action": "play_song", "query": m.group(1)}
    return None


def interpret(llm, text, state):
    """quick() first, then the AI. Returns (action dict, source) where source is 'rule' or 'ai'."""
    hit = quick(text, state)
    if hit:
        return hit, "rule"
    if llm is None:
        raise LLMError("I only know the basic commands until AI is set up (Settings).")
    context = (f"Current volume: {state.get('volume', 60)}. Now playing: {state.get('song') or 'nothing'}. "
               f"Maximized tile: {state.get('maximized') or 'none'}. Watchlist: {', '.join(state.get('watchlist', []))}.")
    if state.get("headlines"):
        context += "\nNews list shown:\n" + "\n".join(f"{i}. {h}" for i, h in enumerate(state["headlines"][:15], 1))
    if state.get("weather"):
        context += f"\nWeather forecast (use it to answer weather questions with an 'answer'): {state['weather']}"
    action = llm.chat_json(SYSTEM, f"{context}\n\nRequest: {text}", timeout=60, max_tokens=300)
    if not isinstance(action, dict) or "action" not in action:
        return {"action": "answer", "text": "Sorry, I didn't get that."}, "ai"
    return action, "ai"


BRIEF_SYSTEM = ("You brief someone out loud on the latest cyber attacks and security news. From the headlines given, "
                "pick the 3 to 4 most significant (major breaches, ransomware, actively exploited flaws, big "
                "vendors). Speak in plain sentences, no lists, no markdown, under 90 words.")


def cyber_brief(llm, headlines):
    if llm is None:
        raise LLMError("no AI")
    return llm.chat(BRIEF_SYSTEM, headlines, timeout=120, max_tokens=400).strip()


EXPLAIN_SYSTEM = ("You explain one security news story to a non-specialist, out loud. Cover: what happened, who or what "
                  "is affected, how the attack or flaw works in simple terms, and what people should do about it (if "
                  "anything). Plain spoken sentences, no lists, no markdown, no URLs, under 130 words. Use only facts "
                  "from the article text; if it doesn't say, don't guess.")
EXPLAIN_NEWS_SYSTEM = ("You explain one news story out loud to a busy listener. Cover: what happened, who is involved, why it "
                       "matters, and what happens next if the article says. Plain spoken sentences, no lists, no "
                       "markdown, no URLs, under 120 words. Use only facts from the article text; don't guess.")


def explain_story(llm, title, text, kind="cyber"):
    if llm is None:
        raise LLMError("Set up AI in Settings to explain stories.")
    system = EXPLAIN_NEWS_SYSTEM if kind == "news" else EXPLAIN_SYSTEM
    return llm.chat(system, f"Headline: {title}\n\nArticle:\n{text}", timeout=180, max_tokens=600).strip()


def find_story(news, action):
    """The story an explain_story action points at: by position, else by the most headline words matched."""
    if not news:
        return None
    idx = action.get("index")
    if isinstance(idx, (int, float)) or (isinstance(idx, str) and idx.isdigit()):
        i = int(idx) - 1
        return news[i] if 0 <= i < len(news) else None
    words = set(re.findall(r"\w{3,}", (action.get("query") or "").lower()))
    if not words:
        return news[0]
    best = max(news, key=lambda it: len(words & set(re.findall(r"\w{3,}", it["title"].lower()))))
    return best if words & set(re.findall(r"\w{3,}", best["title"].lower())) else None
