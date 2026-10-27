// Builds the deliverable: ../../lab3/lab3_FR_NFR.docx
//   npm install docx && python3 gen_usecase.py && qlmanage -t -s 1860 -o . use_case_diagram.svg
//   mv use_case_diagram.svg.png use_case_diagram.png && node build_doc.js
const fs = require("fs");
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell, WidthType,
  AlignmentType, BorderStyle, ShadingType, ImageRun, PageBreak, HeadingLevel,
  Footer, PageNumber, TableLayoutType,
} = require("docx");

const FONT = "Times New Roman";
const SIZE = 24;
const TEAM = "SC2006 Team 5";
const DATE = "26 Oct 2026";
const CONTENT_W = 9026;

const p = (text, opts = {}) =>
  new Paragraph({
    alignment: opts.align,
    spacing: { before: opts.before ?? 0, after: opts.after ?? 80, line: 276 },
    children: [new TextRun({ text, bold: opts.bold, italics: opts.italics, font: FONT, size: opts.size ?? SIZE })],
  });

const heading = (text, level = 1) =>
  new Paragraph({
    heading: level === 1 ? HeadingLevel.HEADING_1 : HeadingLevel.HEADING_2,
    alignment: level === 1 ? AlignmentType.CENTER : AlignmentType.LEFT,
    spacing: { before: level === 1 ? 0 : 240, after: 200 },
    keepNext: true,
    children: [new TextRun({ text, bold: true, font: FONT, color: "000000", size: level === 1 ? 36 : 28 })],
  });

const pageBreak = () => new Paragraph({ children: [new PageBreak()] });
const border = { style: BorderStyle.SINGLE, size: 8, color: "000000" };
const borders = { top: border, bottom: border, left: border, right: border };
const margins = { top: 90, bottom: 90, left: 140, right: 140 };

function cell(content, width, { bold = false, align = AlignmentType.LEFT, span = 1, shade = null } = {}) {
  const lines = Array.isArray(content) ? content : [content];
  return new TableCell({
    width: { size: width, type: WidthType.DXA },
    columnSpan: span, borders, margins,
    shading: shade ? { type: ShadingType.CLEAR, color: "auto", fill: shade } : undefined,
    children: lines.map((t, i) =>
      new Paragraph({
        alignment: align,
        spacing: { before: 0, after: i === lines.length - 1 ? 0 : 40, line: 276 },
        children: [new TextRun({ text: t, bold, font: FONT, size: SIZE })],
      })),
  });
}

const FR = [
  ["1.", "Users must be able to compare neighbourhoods (Where to Live)."],
  ["1.1", "Users must select neighbourhoods."],
  ["1.1.1", "The system must display the in-scope neighbourhoods, drawn from the URA Planning Areas defined in the Data Dictionary."],
  ["1.1.1.1", "The system must allow a neighbourhood to be selected either from a map of the in-scope neighbourhoods or from an equivalent list, and must remain usable when the map cannot be displayed."],
  ["1.1.2", "The user must select the neighbourhoods to compare."],
  ["1.1.2.1", "The user must select at least 2 and at most 4 neighbourhoods."],
  ["1.1.2.2", "Where the user attempts to proceed with fewer than 2 or more than 4 neighbourhoods selected, the system must block the comparison and state the allowed range."],
  ["1.2", "Users may configure the comparison factors."],
  ["1.2.1", "The system must display the six comparison factors defined in the Data Dictionary."],
  ["1.2.2", "The user may include or exclude each comparison factor."],
  ["1.2.2.1", "All comparison factors except commute must be included by default; commute must be excluded by default."],
  ["1.2.2.2", "The user must include at least one comparison factor."],
  ["1.2.2.3", "The system must not request factor options for, calculate, or check data availability for an excluded comparison factor."],
  ["1.2.3", "The user may specify the importance weight of each included comparison factor."],
  ["1.2.3.1", "The importance weight must be expressed on a scale of 1 (least important) to 10 (essential)."],
  ["1.2.3.2", "Where the user does not specify an importance weight for an included comparison factor, the system must apply a default weight of 5."],
  ["1.2.4", "The user may specify the preferred mode of public transport where public transport is included."],
  ["1.2.4.1", "The preferred mode must be one of MRT/LRT, Bus, or Either. The default must be Either."],
  ["1.2.4.2", "Where bus data is unavailable, the factor must be rail-only and must offer no mode choice."],
  ["1.2.5", "The user must specify housing options where housing affordability is included."],
  ["1.2.5.1", "The user must select one flat type: 3-room, 4-room, 5-room, or Executive."],
  ["1.2.5.2", "The user must specify a budget range consisting of a minimum and a maximum resale price."],
  ["1.2.5.3", "The minimum price must not exceed the maximum price."],
  ["1.2.5.4", "The user may specify a minimum remaining lease of 60, 70, or 80 years."],
  ["1.2.6", "The user may select the amenity types to be counted where amenities is included."],
  ["1.2.6.1", "The amenity types must be supermarkets, hawker centres, shopping malls, libraries, gyms and sports facilities, and cafés."],
  ["1.2.6.2", "All amenity types must be selected by default, and at least one amenity type must remain selected."],
  ["1.2.7", "The user may select the healthcare facility type where healthcare is included."],
  ["1.2.7.1", "The facility type must be one of GP clinics, polyclinics, or hospitals. The default must be GP clinics."],
  ["1.2.8", "The user must specify commute details where commute is included."],
  ["1.2.8.1", "On including commute, the system must display a destination postal code field."],
  ["1.2.8.2", "Where commute is included, the user must enter a 6-digit destination postal code and select a commute mode of public transport or drive. The default mode must be public transport."],
  ["1.2.8.3", "The system must reject a destination postal code that cannot be resolved to a location in Singapore."],
  ["1.2.9", "Greenery must have no factor options other than its importance weight."],
  ["1.3", "Users must be able to view neighbourhood comparisons."],
  ["1.3.1", "The system must retrieve the neighbourhood data for the selected neighbourhoods from the data snapshot."],
  ["1.3.2", "The system must calculate a category score from 0 to 10 for each included comparison factor for each selected neighbourhood, using the user's factor options, as defined in the Data Dictionary."],
  ["1.3.2.1", "For public transport, amenities, greenery and healthcare, the category score must be derived from the neighbourhood's percentile rank among all in-scope neighbourhoods."],
  ["1.3.2.2", "For housing affordability, the category score must be the percentage of the neighbourhood's resale transactions in the last 12 months matching the user's flat type and minimum remaining lease whose price falls within the user's budget, divided by 10."],
  ["1.3.2.3", "For commute, the category score must be 10 for a median travel time of 20 minutes or less, 0 for 80 minutes or more, and linearly interpolated between these values."],
  ["1.3.2.4", "Accessibility measures must be calculated for each HDB block and aggregated to the neighbourhood as flat-weighted values."],
  ["1.3.3", "Where data for an included comparison factor is unavailable for any selected neighbourhood, the system must exclude that factor for all selected neighbourhoods and must name the neighbourhood and the reason."],
  ["1.3.3.1", "Housing affordability data must be treated as unavailable where fewer than 10 matching resale transactions exist for a neighbourhood."],
  ["1.3.3.2", "Where every included comparison factor is excluded under 1.3.3, the system must not produce a ranking and must ask the user to change the included factors."],
  ["1.3.3.3", "The system must warn the user, before the comparison is submitted, where the current selection would cause a comparison factor to be excluded for lack of data."],
  ["1.3.4", "The system must calculate an overall neighbourhood score for each selected neighbourhood as the weighted mean of its included category scores."],
  ["1.3.5", "The system must rank the selected neighbourhoods by overall neighbourhood score, rounded to 1 decimal place."],
  ["1.3.5.1", "Where two or more neighbourhoods receive an equal overall neighbourhood score at 1 decimal place, the system must display them as joint-ranked rather than arbitrarily ordering them."],
  ["1.4", "Users must receive a neighbourhood recommendation."],
  ["1.4.1", "The system must identify the highest-ranked neighbourhood as the recommendation."],
  ["1.4.1.1", "Where the highest rank is joint, the system must present all joint-ranked neighbourhoods as the recommendation."],
  ["1.4.2", "The system must display the recommended neighbourhood with a one-sentence explanation naming the comparison factor with the largest marginal contribution over the runner-up."],
  ["1.4.2.1", "The marginal contribution of a comparison factor must be calculated as (recommended neighbourhood's category score − runner-up's category score) × the user's importance weight."],
  ["1.4.3", "Where the overall neighbourhood scores of the two highest-ranked neighbourhoods differ by 0.2 or less, the system must indicate that they are nearly tied."],
  ["1.4.4", "The user may request a score breakdown."],
  ["1.4.4.1", "The score breakdown must list, for each included comparison factor, the importance weight, the category scores and raw values of the recommended neighbourhood and the runner-up, and the marginal contribution, sorted by absolute marginal contribution."],
  ["1.4.4.2", "The score breakdown must display the overall neighbourhood score formula with the user's importance weights substituted, and at least one worked line."],
  ["1.4.4.3", "The score breakdown must list each excluded comparison factor and state whether it was excluded by the user or because data was unavailable."],
  ["1.5", "Users must be able to view comparison results visually."],
  ["1.5.1", "The system must display the selected neighbourhoods as a ranked list showing each neighbourhood's overall neighbourhood score and category scores."],
  ["1.5.2", "The system must display the raw value behind each category score."],
  ["1.5.3", "The system must display the category scores as a grouped bar chart on the results page. A radar chart may be offered in addition but must not be the only chart."],
  ["1.5.3.1", "A neighbourhood must be shown in the same colour in the chart, the map and the ranked list, and that colour must not change when weights change."],
  ["1.5.4", "The system must display the boundaries of the selected neighbourhoods on a map, rendered from locally held Planning Area boundary geometry."],
  ["1.5.5", "The system must display a note for any selected neighbourhood with fewer than 10 HDB blocks, stating the number of blocks and flats on which its scores are based."],
  ["1.5.5.1", "The system must display a note for any selected neighbourhood whose flat-weighted median distance to a rail exit exceeds 1,500 m, naming the date of the station data. The note must be shown only where public transport is included."],
  ["1.5.6", "The system must display the generation date of the data snapshot used."],
  ["1.6", "Users may continue from a recommendation to the other features."],
  ["1.6.1", "The system must offer, from the recommended neighbourhood, a link to find places to eat in that neighbourhood."],
  ["1.6.2", "Where the highest rank is joint, the system must offer that link for each joint-ranked neighbourhood."],

  ["2.", "Users must be able to find events (Where to Lepak)."],
  ["2.1", "Users must specify event search criteria."],
  ["2.1.1", "The system must display the event categories defined in the Data Dictionary, with a control to select all of them at once."],
  ["2.1.1.1", "The system may reveal the remaining search criteria only after at least one event category has been selected, and must display all criteria where that behaviour is unavailable."],
  ["2.1.2", "The user must select at least 1 and at most 8 event categories."],
  ["2.1.3", "The user must select a date option of today, tomorrow, this weekend, the next 7 days, or the next 30 days."],
  ["2.1.4", "The user must provide a starting point by entering a postal code or by allowing the system to use the device location."],
  ["2.1.4.1", "Where device location permission is denied, the system must request a postal code instead."],
  ["2.1.4.2", "The system must reject a postal code that cannot be resolved to a location in Singapore."],
  ["2.1.5", "The user must select a travel mode of public transport, drive, or walk."],
  ["2.1.6", "The user must select a maximum travel time. The options must be 15, 30, 45, 60 and 90 minutes, and the system must accept any value from 5 to 180 minutes."],
  ["2.2", "The system must search for matching events."],
  ["2.2.1", "The system must retrieve the stored events in the selected event categories whose dates overlap the selected date option."],
  ["2.2.2", "The system must exclude events whose straight-line distance from the starting point cannot be covered within the maximum travel time."],
  ["2.2.3", "Where more than 25 events remain after 2.2.2, the system must calculate routes to the 25 nearest and must state how many events were within reach."],
  ["2.2.4", "The system must calculate the travel time and route from the starting point to each remaining event using the selected travel mode."],
  ["2.2.5", "The system must exclude events whose travel time exceeds the maximum travel time."],
  ["2.2.6", "Where a route cannot be calculated for an event, the system must display the straight-line distance labelled as an estimate instead of a travel time, and must place that event after the routed events when results are sorted by travel time."],
  ["2.2.7", "The system must display a progress indicator for any request that has not completed within 320 milliseconds, and must return control to the user if the request has not completed within 60 seconds."],
  ["2.3", "Users must be able to view event results."],
  ["2.3.1", "The system must display event results in pages of 10."],
  ["2.3.2", "Each event result must show the title, event category, date and time, venue, travel time, route summary and a link to the source post."],
  ["2.3.2.1", "Each event result must show a freely licensed photograph of its venue where one is held, with its source credited, and generated category artwork otherwise."],
  ["2.3.3", "Where no events match the search criteria, the system must display a message suggesting a wider date range or a longer maximum travel time."],
  ["2.3.4", "The system must display how long ago events were last updated."],
  ["2.3.4.1", "Where events have not been updated for more than 24 hours, the system must display a warning."],
  ["2.3.4.2", "An ingestion run in which a channel, the LLM Service or the location service failed must not count as an update."],
  ["2.4", "Users may sort and filter event results."],
  ["2.4.1", "The user may sort event results by shortest travel time, soonest, or recently added. The default must be shortest travel time."],
  ["2.4.2", "The user may hide and show each selected event category independently of the others."],
  ["2.4.3", "Sorting and hiding results must not trigger a new search or any external data request."],
  ["2.5", "Users may view the route to an event."],
  ["2.5.1", "The user may select an event result to view its route."],
  ["2.5.2", "The system must display a map showing the starting point, the venue and the route, together with step-by-step directions naming the stops at which the traveller boards, alights and changes."],
  ["2.5.2.1", "Where a public transport journey is too short to return an itinerary, the system must display a walking route labelled as a walking route."],
  ["2.5.2.2", "Where no route is available, the system must display the starting point and the venue on the map with the estimated straight-line distance."],
  ["2.5.3", "When the user returns to the results, the system must restore the previous sort order, hidden categories and page."],
  ["2.6", "Users travelling by car must be shown parking availability."],
  ["2.6.1", "Where the travel mode is drive, the system must display for each result the number of carparks within 500 m of the venue and their available lots."],
  ["2.6.2", "Displayed parking availability must be no older than 2 minutes."],
  ["2.6.3", "Where no carpark with live availability lies within 500 m of a venue, the system must state that none was found."],
  ["2.6.4", "Where parking availability cannot be retrieved, the system must state that parking information is unavailable and must continue to display the results."],
  ["2.7", "Users may continue from an event to the other features."],
  ["2.7.1", "The system must offer, from an event's details, a link to find places to eat near that event."],

  ["3.", "Users must be able to find places to eat (Where to Eat)."],
  ["3.1", "Users must specify what they are looking for."],
  ["3.1.1", "The system must display the search form for places to eat."],
  ["3.1.2", "The user may select cuisine groups from the eight defined in the Data Dictionary."],
  ["3.1.3", "The user may select the kinds of place to include, from hawker centres, food courts and kopitiams; cafés and fast food; and restaurants."],
  ["3.1.4", "The user must select a mealtime of now, breakfast, lunch, dinner or supper, which determines the time at which opening status and travel are assessed."],
  ["3.1.5", "The user must select a travel mode of public transport, drive, or walk, and a maximum travel time from 10, 15, 20, 30 or 45 minutes, with any value from 5 to 90 minutes accepted."],
  ["3.1.6", "The user must provide a starting point by entering a postal code or by allowing the system to use the device location."],
  ["3.1.6.1", "The system must reject a postal code that cannot be resolved to a location in Singapore, and must ask for another."],
  ["3.2", "The system must search for matching places."],
  ["3.2.1", "The system must select places matching the selected cuisine groups and kinds of place."],
  ["3.2.2", "The system must exclude places whose straight-line distance from the starting point cannot be covered within the maximum travel time."],
  ["3.2.3", "Where more than 25 places remain, the system must calculate routes to the 25 nearest and must state how many were timed."],
  ["3.2.4", "Where a route cannot be calculated for a place, the system must display the straight-line distance labelled as an estimate."],
  ["3.3", "Users must be able to view the places found."],
  ["3.3.1", "Each result must show the name, kind of place, cuisine groups, opening status at the selected mealtime and, where a journey was calculated, the travel time."],
  ["3.3.2", "A food destination must show the number of stalls it holds where that is known."],
  ["3.3.3", "Where ratings are configured, each result must show its rating and review count, with the source credited and linked."],
  ["3.3.3.1", "The system must count rating lookups before each call and must stop making them once the configured daily cap is reached."],
  ["3.3.3.2", "Where ratings are unavailable, results must be displayed without them and the sort by rating must not be offered."],
  ["3.3.3.3", "The system must not store rating data. Only the place identifier required to request a rating may be stored."],
  ["3.3.4", "Where a cuisine filter is active, places with no cuisine listed must be displayed after every matching place, labelled as not listed, and must be hideable by the user."],
  ["3.3.4.1", "The system must state the measured coverage of cuisine and opening-hours data."],
  ["3.3.5", "A place with a corresponding Wikipedia article must show a badge indicating that it is notable, worded so that it does not imply a judgement of quality."],
  ["3.3.6", "The price tier must be described in words and must not be displayed as currency symbols, as no price data is held."],
  ["3.4", "Users may sort and filter the places found."],
  ["3.4.1", "The user may sort the results by nearest, open first, most variety, or highest rated where ratings are available. The default must be nearest."],
  ["3.4.2", "The user may hide and show each cuisine group independently of the others."],
  ["3.4.3", "Sorting and hiding results must not trigger a new search or any external data request."],
  ["3.5", "Users may view a place's details."],
  ["3.5.1", "The user may select a place to view its details."],
  ["3.5.2", "The details must show the name, kind of place, cuisine groups, opening hours and address, with the rating and notability badge where they apply."],
  ["3.5.3", "The details must show the place on a map, together with the route and step-by-step directions where a route was calculated."],
  ["3.5.4", "When the user returns to the results, the system must restore the previous sort order, hidden cuisine groups and page."],
  ["3.6", "Users may enter Where to Eat from the other features."],
  ["3.6.1", "Where the user enters from an event, the system must use that event's location as the starting point, name it on the search form, and allow the user to clear it."],
  ["3.6.2", "Where the user enters from a neighbourhood recommendation, the system must list the places in that neighbourhood and state how many there are, and must not request a starting point, travel mode or maximum travel time."],
  ["3.6.2.1", "In that case the system must not calculate any route, and must offer sorting by most variety or alphabetically."],

  ["4.", "The system must maintain neighbourhood, event and place data."],
  ["4.1", "The system must maintain the data snapshot."],
  ["4.1.1", "The system must provide a data refresh procedure, run by the Maintainer, that regenerates the data snapshot from the Data Sources."],
  ["4.1.2", "The data snapshot must be refreshed at least every 3 months."],
  ["4.1.3", "The system must validate a new data snapshot before it replaces the active data snapshot."],
  ["4.1.4", "Where a refresh or its validation fails, the system must continue operating using the most recent successful data snapshot."],
  ["4.1.5", "Each data snapshot must record its generation date and the date of each source dataset used."],
  ["4.1.6", "Where the active data snapshot is older than 12 months, the system must display a warning with neighbourhood comparison results."],
  ["4.1.7", "The system must not require any bulk Data Source to be reachable while serving users."],
  ["4.2", "The system must ingest events."],
  ["4.2.1", "The system must collect new posts from the Telegram Channel List every 6 hours when the ingestion schedule is enabled, and must allow an ingestion run to be started on demand."],
  ["4.2.2", "The system must discard posts containing no date-like text before sending any post to the LLM Service."],
  ["4.2.3", "The system must extract event details from each remaining post using the LLM Service, in the Event format defined in the Data Dictionary."],
  ["4.2.3.1", "Post text must be supplied to the LLM Service as data to be extracted from, and the system must not act on any instruction contained in a post."],
  ["4.2.4", "The system must discard any extracted event that has no title, start date-time or venue, whose event category is not defined in the Data Dictionary, or that has already ended."],
  ["4.2.5", "The system must discard any event whose venue cannot be resolved to coordinates in Singapore, and must record the title, venue and address that were extracted."],
  ["4.2.6", "The system must merge duplicate events, defined as events on the same date with similar titles and venues within 200 m, retaining all source links."],
  ["4.2.7", "The system must store only the extracted event details and the link to the source post, and must not store raw message text or the identity of the poster."],
  ["4.2.8", "Where a Telegram channel, the LLM Service or the location service is unavailable, the system must retry at the next run without losing unprocessed posts, and must not stop the ingestion schedule."],
  ["4.2.9", "The system must remove events that have ended at least once per day."],
  ["4.3", "The system must maintain the place list."],
  ["4.3.1", "The system must provide a place-list build, run by the Maintainer, that regenerates the place list from the Data Sources."],
  ["4.3.2", "The build must exclude places outside Singapore, places without a name, and duplicates of a food destination."],
  ["4.3.3", "The build must assign each place to a cuisine group, a kind of place, a price tier and a Planning Area."],
  ["4.3.4", "The build must record the measured coverage of cuisine and opening-hours data."],
  ["4.3.5", "The build must match a place to a Wikipedia article only where every word of the place's name appears in the article's title."],
];

function frParagraphs() {
  const out = [];
  for (const [id, text] of FR) {
    const depth = id.endsWith(".") ? 0 : id.split(".").length - 1;
    const bold = depth <= 1;
    if (depth === 0 && out.length) out.push(p("", { after: 120 }));
    if (depth === 1) out.push(p("", { after: 0 }));
    out.push(new Paragraph({
      spacing: { before: 0, after: 60, line: 276 },
      indent: { left: depth * 360 },
      keepNext: depth <= 1,
      children: [new TextRun({ text: `${id} ${text}`, bold, font: FONT, size: SIZE })],
    }));
  }
  return out;
}

const NFR = [
  ["Usability", "At least 4 out of 5 first-time users in a moderated usability test shall be able to complete a full neighbourhood comparison within 10 minutes, and a full event or place search within 5 minutes, without external help. The system shall indicate progress for any request that has not completed within 320 milliseconds, and shall not display a progress indicator for requests that complete sooner."],
  ["Performance", "The system shall display neighbourhood comparison results within 3 seconds of submission, or within 10 seconds where the commute factor is included. For searches that require routing, the 90th percentile of responses shall be within 8 seconds, with the measured median and worst case published alongside; the target is stated as a percentile because the tail is the routing service's latency rather than the system's. Re-sorted or filtered results shall be displayed within 1 second."],
  ["Reliability", "The system shall handle invalid user input and the unavailability of any external service (OneMap API, LTA DataMall, Telegram, the LLM Service, Google Places, Data Sources) without crashing or terminating unexpectedly, and shall degrade as specified in the functional requirements. The system shall serve concurrent requests from the same or different users correctly. Where every routing call in a request fails, the system shall record a warning distinguishing a total failure from ordinary degradation."],
  ["Supportability", "The system shall be built from modular components, such that a new comparison factor, event category, data source or external service provider can be added or replaced without modifying the core scoring engine. Demonstrated twice: replacing the LLM Service provider changed one adapter class and no other production code; adding a third feature added new modules with only small additive changes at the shared seams, and required no change to any existing test."],
  ["Scalability", "The system should continue to meet the Performance targets above as the number of in-scope neighbourhoods, stored events and places grows. Where the number of candidates for routing exceeds the configured budget, the system shall route the nearest candidates and state how many were timed, rather than refusing the request."],
  ["Accuracy", "Given the same data snapshot and user inputs, a manual recalculation using the documented scoring formulas shall equal the system's category scores and overall neighbourhood scores to 1 decimal place (±0.05). All displayed scores shall be rounded half-up."],
  ["Transparency", "The system shall display enough information about how a recommendation was calculated that a user can identify which comparison factors drove the result. The system shall state the age, source and measured coverage of the data behind a displayed figure wherever these are material, shall label estimated values as estimates, and shall link every event result to its source post."],
  ["Data Currency", "Under normal operation, events posted to the Telegram Channel List shall be available to users within 6 hours of posting, displayed parking availability shall be no older than 2 minutes, and the data snapshot shall be no older than 3 months."],
  ["Compatibility", "The system shall operate correctly on the current stable versions of Google Chrome and Mozilla Firefox on desktop Windows and macOS, and on current mobile browsers at a viewport width of 390 pixels or more, with no horizontal scrolling of the page."],
  ["Security", "The system shall not require account creation and shall not collect personally identifiable information. Importance weights, factor options, postal codes and device location shall be held only for the current session and shall not be written to a URL, a cookie, a log or disk. API credentials and access tokens shall be held on the server and never sent to the browser or recorded in a log. Text extracted from public posts shall be treated as untrusted input: it shall be validated before storage and escaped on display, and the system shall not act on instructions contained within it."],
  ["Compliance", "The system shall display attribution for OneMap (SLA), OpenStreetMap contributors and data.gov.sg on every page; shall credit the source and licence of each venue photograph beside the photograph; and shall credit and link the source of any rating it displays. The system shall store only data that the source's terms permit it to store."],
];

const DD = [
  ["GoWhere", "The system described by this document: a web application with three features — Where to Live, Where to Lepak and Where to Eat — built on shared location and routing services."],
  ["Where to Live", "The feature that compares 2 to 4 neighbourhoods against the user's included comparison factors, importance weights and factor options, and recommends one."],
  ["Where to Lepak", "The feature (from the Singlish term lepak, meaning to relax or hang out) that finds upcoming events matching the user's event categories, date option and travel limits, and shows how to travel to them."],
  ["Where to Eat", "The feature that finds places to eat near a starting point, or lists every place to eat in one neighbourhood. Unlike Where to Lepak it covers permanent establishments rather than time-bound events: a food festival this weekend is an event, a hawker centre is a place."],
  ["Neighbourhood", "A URA Planning Area that contains at least one HDB residential block (an in-scope Planning Area). 32 of Singapore's 55 Planning Areas are in scope."],
  ["Comparison Factor", "One of the six criteria used to evaluate neighbourhoods: public transport, housing affordability, amenities, greenery, healthcare and commute."],
  ["Included Factor", "A comparison factor the user has chosen to use in a comparison. An excluded factor is not calculated and does not affect any score."],
  ["Importance Weight", "A value from 1 (least important) to 10 (essential) that the user assigns to an included factor. The default is 5."],
  ["Factor Options", "The user's choices that change how an included factor is measured: preferred public transport mode; flat type, budget range and minimum remaining lease; amenity types; healthcare facility type; and commute destination and mode."],
  ["Public Transport", "Walking access to rail, service variety by bus, or whichever scores higher. MRT/LRT: 0.7 × Percentile Rank of the flat-weighted percentage of flats within a 10-minute walk of an exit + 0.3 × Percentile Rank of the flat-weighted median Walking Time (shorter is better). Bus: 0.7 × Percentile Rank of the flat-weighted median number of distinct bus services within 400 m + 0.3 × Percentile Rank of the flat-weighted median Walking Time to the nearest Qualifying Bus Stop. Either: the higher of the two scores."],
  ["Qualifying Bus Stop", "A bus stop served by at least 3 bus services."],
  ["Housing Affordability", "The percentage of a neighbourhood's HDB resale transactions in the last 12 complete calendar months, matching the user's flat type and minimum remaining lease, whose price falls within the user's budget range. Category Score = percentage ÷ 10."],
  ["Amenities", "The flat-weighted mean number of the user's selected amenity types within 800 m of each HDB block, with each amenity type counted up to a maximum of 3. Category Score = Percentile Rank."],
  ["Greenery", "The flat-weighted percentage of flats within 400 m of the edge of a park or park connector. Category Score = Percentile Rank."],
  ["Healthcare", "The flat-weighted median distance from HDB blocks to the nearest facility of the user's selected type. Category Score = Percentile Rank (shorter is better). Hospitals means the 9 public acute general hospitals, where emergency cases are taken."],
  ["Commute", "The travel time from a neighbourhood's Commute Origin to the user's destination by the selected mode, for public transport departing at 08:30 on the next weekday. Category Score = 10 at 20 minutes or less, 0 at 80 minutes or more, linearly interpolated between."],
  ["Commute Origin", "The HDB block nearest a neighbourhood's flat-weighted centroid, used as the starting point for that neighbourhood's commute."],
  ["HDB Block", "A residential block listed in HDB Property Information, with its resolved coordinates and number of flats. 10,796 of the 13,357 blocks in the dataset are residential, holding 1,175,956 dwelling units."],
  ["Flat-Weighted", "Aggregated across a neighbourhood's HDB blocks with each block counted in proportion to its number of flats."],
  ["Walking Time", "Straight-line distance × 1.39 (the calibrated detour factor) ÷ 80 metres per minute."],
  ["Data Snapshot", "The validated set of neighbourhood data produced by the data refresh procedure, recording its generation date and the date of each source dataset. Where to Live reads only from the active data snapshot at runtime."],
  ["Category Score", "A value from 0 to 10 representing how well a neighbourhood performs on a single included factor, before importance weights are applied."],
  ["Percentile Rank", "A neighbourhood's position among the in-scope neighbourhoods on a measure, scaled to 0–10: (average rank − 1) ÷ (number of neighbourhoods − 1) × 10, where rank 1 is the worst-performing. Ties take the average rank, and the rank is computed only among neighbourhoods that have data for that factor."],
  ["Overall Neighbourhood Score", "Σ (Category Score × Importance Weight) ÷ Σ (Importance Weight), over the included factors not excluded for unavailable data. A value from 0 to 10, rounded half-up to 1 decimal place for ranking."],
  ["Joint-Ranked", "The ranking given to two or more neighbourhoods whose Overall Neighbourhood Scores are equal at 1 decimal place."],
  ["Marginal Contribution", "(Recommended neighbourhood's Category Score − runner-up's Category Score) × Importance Weight. A positive value favours the recommended neighbourhood; a negative value favours the runner-up."],
  ["Recommendation", "The highest-ranked selected neighbourhood, or all joint-ranked neighbourhoods at the highest rank, together with the comparison factor with the largest Marginal Contribution."],
  ["Score Breakdown", "A detailed view listing each included factor's Importance Weight, Category Scores, raw values and Marginal Contribution, the overall score formula with the user's weights substituted, and every excluded factor with its reason."],
  ["Event", "An upcoming activity extracted from a Telegram post: title, Event Category, start date-time, end date-time (optional), venue name, address, summary, resolved coordinates, Planning Area, and link(s) to the source post(s)."],
  ["Event Category", "One of: Food & Markets, Arts & Culture, Music & Performances, Sports & Fitness, Family & Kids, Workshops & Classes, Community, and Sales & Pop-ups."],
  ["Venue Photograph", "A freely licensed photograph of an event's venue, taken from the Wikipedia article at the venue's coordinates and stored locally with its artist and licence. Where no photograph is held, generated category artwork is shown instead."],
  ["Place", "An establishment where food is served: an individual eatery, or a Food Destination. Each holds a name, kind of place, cuisine groups, price tier, opening hours where known, coordinates, Planning Area and source."],
  ["Food Destination", "A place holding many stalls under one roof — a hawker centre, food court or market — shown as a single result carrying its stall count where known."],
  ["Cuisine Group", "One of eight groups mapped from the source's cuisine tags and the place's name: Local, Chinese, Malay & Indonesian, Indian, Japanese & Korean, Thai & Vietnamese, Western, and Cafés & Desserts. A place with no recognised tag is shown as having no cuisine listed."],
  ["Price Tier", "A description of the kind of venue rather than a measured price: hawker centres, food courts and kopitiams; cafés and fast food; or restaurants. Shown in words, never as currency symbols, because no price data is held."],
  ["Mealtime", "The time at which opening status and travel are assessed: now, breakfast, lunch, dinner or supper, taken as the next occurrence of that mealtime."],
  ["Rating", "A place's rating and review count, obtained from Google Places at the time of display. Ratings are never stored; only the place identifier needed to request one is held, and lookups stop at a configured daily cap."],
  ["Place List", "The validated set of places produced by the place-list build, recording the measured coverage of cuisine and opening-hours data. Where to Eat reads only from the place list at runtime."],
  ["Starting Point", "The location from which travel is calculated — a postal code, the device location, or an event's location when the user enters Where to Eat from an event — held for the current session only."],
  ["Travel Mode", "The means of travel used for routing: public transport, drive or walk; public transport or drive for commute."],
  ["Route", "The travel time, distance, route summary and step-by-step directions between two locations for a Travel Mode, obtained from OneMap API."],
  ["Parking Availability", "The number of available lots at carparks within 500 m of a venue, obtained from LTA DataMall, no more than 2 minutes old."],
  ["Telegram Channel List", "The list of public Telegram broadcast channels, maintained by the project team in configuration, from which events are collected."],
  ["Maintainer", "A project team member who runs the data refresh procedure and the place-list build, and maintains the Telegram Channel List."],
  ["Data Sources", "The bulk sources read only by the offline builds: data.gov.sg and government agency datasets (URA, HDB, LTA, NParks, MOH, NEA, SFA, NLB), LTA DataMall's static datasets, OpenStreetMap, and Wikipedia."],
  ["External Services", "The services called while serving a user: OneMap API (location resolution, routing and base map tiles), LTA DataMall (live carpark availability), Google Places (ratings), Telegram (post collection) and the LLM Service (event extraction). Each is reached through its own adapter with a documented fallback."],
  ["LLM Service", "A large language model API used to extract Event details from Telegram post text."],
  ["Session", "The period for which the user's browser tab remains open. Inputs held for the session are discarded when it ends."],
];

function twoColTable(rows, w1, header) {
  const w2 = CONTENT_W - w1;
  const trs = [];
  if (header) {
    trs.push(new TableRow({
      tableHeader: true,
      children: [cell(header[0], w1, { bold: true, shade: "D9D9D9" }), cell(header[1], w2, { bold: true, shade: "D9D9D9" })],
    }));
  }
  for (const [a, b] of rows) {
    trs.push(new TableRow({ cantSplit: true, children: [cell(a, w1, { bold: true }), cell(b, w2)] }));
  }
  return new Table({ layout: TableLayoutType.FIXED, width: { size: CONTENT_W, type: WidthType.DXA }, columnWidths: [w1, w2], rows: trs });
}

const UC = require("./use_cases.js");
const LW = 2300;

function useCaseTables(uc) {
  const vW = CONTENT_W - LW;
  const R = AlignmentType.RIGHT;
  const half = [2300, 2213, 2300, 2213];
  const header = new Table({
    layout: TableLayoutType.FIXED,
    width: { size: CONTENT_W, type: WidthType.DXA },
    columnWidths: half,
    rows: [
      new TableRow({ cantSplit: true, children: [cell("Use Case ID:", half[0], { bold: true, align: R }), cell(uc.id, half[1] + half[2] + half[3], { span: 3 })] }),
      new TableRow({ cantSplit: true, children: [cell("Use Case Name:", half[0], { bold: true, align: R }), cell(uc.name, half[1] + half[2] + half[3], { span: 3 })] }),
      new TableRow({ cantSplit: true, children: [cell("Created By:", half[0], { bold: true, align: R }), cell(TEAM, half[1]), cell("Last Updated By:", half[2], { bold: true, align: R }), cell(TEAM, half[3])] }),
      new TableRow({ cantSplit: true, children: [cell("Date Created:", half[0], { bold: true, align: R }), cell("8 Sep 2026", half[1]), cell("Date Last Updated:", half[2], { bold: true, align: R }), cell(DATE, half[3])] }),
    ],
  });
  const rows = [
    ["Actor:", uc.actor], ["Description:", uc.desc], ["Preconditions:", uc.pre], ["Postconditions:", uc.post],
    ["Priority:", uc.priority], ["Frequency of Use:", uc.freq], ["Flow of Events:", uc.flow],
    ["Alternative Flows:", uc.alt], ["Exceptions:", uc.exc], ["Includes:", uc.includes],
    ["Special Requirements:", uc.sr], ["Assumptions:", uc.assume], ["Notes and Issues:", uc.notes],
  ];
  const body = new Table({
    layout: TableLayoutType.FIXED,
    width: { size: CONTENT_W, type: WidthType.DXA },
    columnWidths: [LW, vW],
    rows: rows.map(([l, v]) => new TableRow({ children: [cell(l, LW, { bold: true, align: R }), cell(v, vW)] })),
  });
  return [header, p("", { after: 200 }), body];
}

const children = [];
children.push(heading("GoWhere — Functional and Non-Functional Requirements"));
children.push(p("SC2006 Team 5 · Revised " + DATE, { align: AlignmentType.CENTER, italics: true, after: 240 }));
children.push(p("This revision describes the system as built, covering all three features. Where a requirement was changed during implementation, the change and the evidence behind it are recorded in DECISIONS.md in the project repository.", { italics: true, after: 240 }));
children.push(heading("Functional Requirement", 2));
children.push(...frParagraphs());

children.push(pageBreak());
children.push(heading("Non-Functional Requirement", 2));
children.push(twoColTable(NFR, 2000, ["Category", "Requirement"]));

children.push(pageBreak());
children.push(heading("Data Dictionary", 2));
children.push(twoColTable(DD, 2600, ["Term", "Definition"]));

children.push(pageBreak());
children.push(heading("Use Case Diagram", 2));
const img = fs.readFileSync("use_case_diagram.png");
children.push(new Paragraph({
  alignment: AlignmentType.CENTER,
  children: [new ImageRun({ type: "png", data: img, transformation: { width: 620, height: 620 } })],
}));

UC.forEach((uc, i) => {
  children.push(pageBreak());
  if (i === 0) children.push(heading("Use Case Description"));
  children.push(...useCaseTables(uc));
});

const doc = new Document({
  styles: {
    default: {
      document: { run: { font: FONT, size: SIZE } },
      heading1: { run: { font: FONT, color: "000000" } },
      heading2: { run: { font: FONT, color: "000000" } },
    },
  },
  sections: [{
    properties: { page: { size: { width: 11906, height: 16838 }, margin: { top: 1440, bottom: 1440, left: 1440, right: 1440 } } },
    footers: {
      default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ children: [PageNumber.CURRENT], font: FONT, size: 20 })] })] }),
    },
    children,
  }],
});

Packer.toBuffer(doc).then((buf) => {
  fs.writeFileSync("../../lab3/lab3_FR_NFR.docx", buf);
  console.log("written", buf.length);
});
