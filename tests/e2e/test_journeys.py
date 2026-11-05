"""The user journeys of the three features, in a real browser (E2E-1 to E2E-4).

Each test is one path a user takes through several screens, so it checks what the unit
and Flask test-client tests cannot: the HTML, the JavaScript (map picker, category
wheel, dialog) and the server working together, and the session carrying state from one
screen to the next. Fixtures and stand-ins: conftest.py.
"""
import re

from playwright.sync_api import expect

from tests.e2e.conftest import POSTAL


def area(page, name):
    return page.get_by_role("checkbox", name=re.compile(rf"^{name}\b"))


def open_area_list(page):
    """Open the list under the 3D map picker, as a keyboard user does. The list is the
    form's real state; the map only drives it (app.js initAreaPicker). Wait for the map
    first: building it closes the list, which hides the checkboxes from the locators."""
    summary = page.locator("#picker-fallback > summary")
    expect(summary).to_have_text("Or choose from a list")      # the map picker was built
    summary.click()
    expect(page.locator("#picker-fallback")).to_have_attribute("open", "")


def choose_neighbourhoods(page, *names):
    open_area_list(page)
    for name in names:
        area(page, name).check()


def test_e2e_1_live_compare_then_change_the_comparison(page):
    page.goto("/")
    page.locator(".home-card", has_text="Where to Live").click()
    expect(page).to_have_url(re.compile(r"/live$"))

    choose_neighbourhoods(page, "Bedok", "Tampines")
    expect(page.locator("#picker-count")).to_have_text("2 of 2–4 chosen")
    page.get_by_role("button", name="Compare").click()

    expect(page).to_have_url(re.compile(r"/live/results$"))
    rows = page.locator("table.results:not(.breakdown) tr").filter(has=page.locator(".rank-badge"))
    expect(rows).to_have_count(2)
    expect(rows.first.locator(".rank-badge")).to_have_attribute("data-rank", "1")
    expect(page.locator(".recommendation h2")).to_contain_text(re.compile("Bedok|Tampines"))

    page.get_by_role("button", name="See how this was calculated").click()
    dialog = page.locator("dialog#breakdown")
    expect(dialog).to_be_visible()
    expect(dialog).to_contain_text("How the ranking was calculated")
    dialog.get_by_role("button", name="Close").click()
    expect(dialog).to_be_hidden()

    # The comparison is kept in this browser's session, so changing it starts from it.
    page.get_by_role("link", name="Change the comparison").click()
    expect(page).to_have_url(re.compile(r"/live$"))
    expect(page.locator("#picker-count")).to_have_text("2 of 2–4 chosen")
    open_area_list(page)
    expect(area(page, "Bedok")).to_be_checked()
    expect(area(page, "Tampines")).to_be_checked()
    expect(area(page, "Bishan")).not_to_be_checked()


def test_e2e_2_live_rejects_one_neighbourhood_and_says_why(page):
    page.goto("/live")
    choose_neighbourhoods(page, "Bedok")
    page.get_by_role("button", name="Compare").click()

    expect(page).to_have_url(re.compile(r"/live$"))
    expect(page.locator(".note--warning").first).to_have_text("Select 2 to 4 neighbourhoods.")
    open_area_list(page)
    expect(area(page, "Bedok")).to_be_checked()     # input kept


def test_e2e_3_lepak_event_then_where_to_eat_near_it(page):
    page.goto("/lepak")
    rest = page.locator("#lepak-rest")
    expect(rest).to_be_hidden()                     # nothing chosen on the wheel yet
    page.get_by_role("button", name="All categories").click()
    expect(rest).to_be_visible()

    page.get_by_label("When").select_option("month")
    page.get_by_label("At most").select_option("45")
    page.locator("input[name=postal]").fill(POSTAL)
    page.get_by_role("button", name="Find events").click()

    expect(page).to_have_url(re.compile(r"/lepak/results$"))
    expect(page.locator("article").first).to_be_visible()
    # Sorted by travel time: the walking-distance store (9 min) comes first.
    expect(page.locator("article h2").first).to_have_text("JisuLife Global Brand Experience Store")
    page.get_by_role("link", name="Anime Earth", exact=True).click()

    expect(page).to_have_url(re.compile(r"/lepak/events/\d+$"))
    expect(page.locator("h1")).to_have_text("Anime Earth")
    page.get_by_role("link", name="Where to eat near this event").click()

    # Where to Eat, starting from the event: its place came through the session.
    expect(page).to_have_url(re.compile(r"/eat$"))
    expect(page.get_by_text("Near Anime Earth")).to_be_visible()
    page.get_by_label("At most").select_option("45")
    page.get_by_role("button", name="Find places").click()

    expect(page).to_have_url(re.compile(r"/eat/results$"))
    cards = page.locator("article")
    expect(cards.first).to_be_visible()
    first = cards.first.locator("h2 a")
    name = first.inner_text()
    first.click()
    expect(page).to_have_url(re.compile(r"/eat/places/\d+$"))
    expect(page.locator("h1")).to_have_text(name)
    page.get_by_role("link", name="Back to results").click()
    expect(page).to_have_url(re.compile(r"/eat/results"))


def test_e2e_4_each_browser_has_its_own_session(browser, base_url, app):
    """State lives on the server, per session; the cookie carries only an opaque id."""
    alice = browser.new_context(base_url=base_url)
    bob = browser.new_context(base_url=base_url)
    for context in (alice, bob):
        context.route(re.compile(r"^(?!" + re.escape(base_url) + r")"),
                      lambda route: route.abort())
    a, b = alice.new_page(), bob.new_page()

    a.goto("/live")
    choose_neighbourhoods(a, "Bedok", "Tampines")
    a.get_by_role("button", name="Compare").click()
    expect(a).to_have_url(re.compile(r"/live/results$"))

    b.goto("/live/results")                        # nothing compared in this browser
    expect(b).to_have_url(re.compile(r"/live$"))
    open_area_list(b)
    expect(area(b, "Bedok")).not_to_be_checked()

    (cookie,) = alice.cookies()
    assert cookie["name"] == "session" and cookie["httpOnly"]
    signed = app.session_interface.get_signing_serializer(app)
    assert set(signed.loads(cookie["value"])) == {"sid"}

    alice.close()
    bob.close()
