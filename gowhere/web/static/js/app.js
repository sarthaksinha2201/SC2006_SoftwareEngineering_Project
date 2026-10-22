(function () {
  "use strict";

  function readJSON(id) {
    var el = document.getElementById(id);
    if (!el) return null;
    try { return JSON.parse(el.textContent); } catch (e) { return null; }
  }

  function styleForFeature(feature) {
    var props = feature.properties || {};
    if (props.kind === "route") return { color: "#1f1f1d", weight: 4, opacity: 0.9 };
    if (feature.geometry.type === "Polygon" || feature.geometry.type === "MultiPolygon") {
      // The colour comes with the feature and is the one the chart gives this
      // neighbourhood (view_models.py), so chart, map and table agree. It follows the
      // town, not its rank: a rank ramp would recolour everything on a re-weighting.
      var color = props.colour || "#787774";
      return { color: color, weight: 2, fillColor: color, fillOpacity: 0.3 };
    }
    return { color: "#1f1f1d", weight: 2 };
  }

  // Returns an element, never a string: Leaflet inserts string content as HTML, and on
  // the event map the name is a venue taken from a public Telegram post (untrusted).
  function tooltipFor(layer) {
    var p = (layer.feature && layer.feature.properties) || {};
    var el = document.createElement("span");
    el.textContent = (p.name && p.overall !== undefined) ? p.name + ": " + p.overall + " / 10"
                                                          : (p.name || "");
    return el;
  }

  // Where to Live results: planning-area polygons coloured by rank. Event detail: the
  // venue point plus, when this session searched for it, the route line. Basemap tiles
  // are not bundled (can't be, per Sarthak.md); offline, the outlines draw on blank.
  function initMap() {
    var container = document.getElementById("map");
    var data = readJSON("map-data");
    if (!container || !data || !data.features || !data.features.length || typeof L === "undefined") {
      return;
    }
    var map = L.map(container, { scrollWheelZoom: false });
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: "&copy; OpenStreetMap contributors",
      maxZoom: 19
    }).addTo(map);
    var layer = L.geoJSON(data, {
      style: styleForFeature,
      // The starting point is a small filled circle; the venue keeps the default pin.
      pointToLayer: function (feature, latlng) {
        if (feature.properties && feature.properties.kind === "start") {
          return L.circleMarker(latlng, { radius: 7, color: "#fff", weight: 2,
                                          fillColor: "#1f1f1d", fillOpacity: 1 });
        }
        return L.marker(latlng);
      }
    }).bindTooltip(tooltipFor).addTo(map);
    try {
      var bounds = layer.getBounds();
      if (bounds.isValid()) map.fitBounds(bounds, { padding: [16, 16] });
      else throw new Error("empty bounds");
    } catch (e) {
      map.setView([1.3521, 103.8198], 12);   // Singapore, roughly centred
    }
  }

  // Results page: a grouped horizontal bar chart (FR 1.5.3): one group per factor, one
  // bar per neighbourhood. Radar is only a secondary toggle (DECISIONS.md section 16):
  // its enclosed area looks meaningful but is an artefact of the axis order.
  function initChart() {
    var canvas = document.getElementById("scores-chart");
    var data = readJSON("chart-data");
    if (!canvas || !data || typeof Chart === "undefined") return;
    var INK = "#1f1f1d", MUTED = "#787774", RULE = "#eaeaea";
    var FONT = { family: "'SF Pro Display', -apple-system, 'Helvetica Neue', sans-serif",
                 size: 12 };
    var chart = null;
    function draw(type) {
      if (chart) chart.destroy();
      var bar = type === "bar";
      chart = new Chart(canvas, {
        type: type,
        data: {
          labels: data.labels,
          // The colour arrives with the dataset: it follows the neighbourhood, not the
          // rank, so re-weighting the factors never repaints the chart (view_models.py).
          datasets: data.datasets.map(function (d) {
            var c = d.colour;
            return { label: d.label, data: d.data, borderColor: c, pointBackgroundColor: c,
                     backgroundColor: bar ? c : c + "26", borderWidth: bar ? 0 : 2,
                     // A rounded data-end anchored to the baseline, and a surface gap
                     // between adjacent bars so the group reads as separate marks.
                     borderRadius: bar ? 4 : 0, borderSkipped: "start",
                     barPercentage: 0.82, categoryPercentage: 0.72,
                     pointRadius: bar ? 0 : 4 };
          })
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          indexAxis: bar ? "y" : "x",
          // A legend is always present: identity is never carried by colour alone.
          plugins: {
            legend: { position: "top", align: "start",
                      labels: { boxWidth: 10, boxHeight: 10, borderRadius: 2,
                                useBorderRadius: true, color: MUTED, font: FONT,
                                padding: 16 } },
            tooltip: { backgroundColor: INK, titleFont: FONT, bodyFont: FONT,
                       padding: 10, cornerRadius: 6, displayColors: true,
                       boxWidth: 8, boxHeight: 8,
                       callbacks: { label: function (ctx) {
                         return " " + ctx.dataset.label + "  " + ctx.parsed[bar ? "x" : "r"]
                                + " / 10";
                       } } }
          },
          scales: bar
            // Recessive axes: one hairline grid on the measure axis, none on the
            // category axis, no axis borders.
            ? { x: { min: 0, max: 10, ticks: { stepSize: 2, color: MUTED, font: FONT },
                     grid: { color: RULE, drawTicks: false },
                     border: { display: false } },
                y: { ticks: { color: INK, font: FONT }, grid: { display: false },
                     border: { display: false } } }
            : { r: { min: 0, max: 10,
                     ticks: { stepSize: 2, color: MUTED, font: FONT, backdropColor: "transparent" },
                     grid: { color: RULE }, angleLines: { color: RULE },
                     pointLabels: { color: INK, font: FONT } } }
        }
      });
      document.querySelectorAll("[data-chart-type]").forEach(function (b) {
        var on = b.getAttribute("data-chart-type") === type;
        b.classList.toggle("is-selected", on);
        b.setAttribute("aria-pressed", on ? "true" : "false");
      });
    }
    document.querySelectorAll("[data-chart-type]").forEach(function (b) {
      b.addEventListener("click", function () { draw(b.getAttribute("data-chart-type")); });
    });
    draw("bar");
  }

  function initDialogs() {
    document.querySelectorAll("[data-open-dialog]").forEach(function (btn) {
      var dialog = document.getElementById(btn.getAttribute("data-open-dialog"));
      if (dialog) btn.addEventListener("click", function () { dialog.showModal(); });
    });
    document.querySelectorAll("[data-close-dialog]").forEach(function (btn) {
      var dialog = btn.closest("dialog");
      if (dialog) btn.addEventListener("click", function () { dialog.close(); });
    });
  }

  // "Use my location" (Where to Lepak): fills the hidden lat/lon fields from the
  // browser so the postal code field is never required. Neither goes in a URL.
  function initGeolocation() {
    var radio = document.querySelector('input[name="origin"][value="here"]');
    if (!radio || !navigator.geolocation) return;
    radio.addEventListener("change", function () {
      navigator.geolocation.getCurrentPosition(function (pos) {
        document.querySelector('input[name="lat"]').value = pos.coords.latitude;
        document.querySelector('input[name="lon"]').value = pos.coords.longitude;
      });
    });
  }

  // Where to Live setup: an excluded factor is greyed out; switching Commute on reveals
  // its destination postal code field (and switching it off hides it again).
  function initFactorToggles() {
    document.querySelectorAll("fieldset[data-factor]").forEach(function (fs) {
      var box = fs.querySelector('input[name="include_' + fs.getAttribute("data-factor") + '"]');
      if (!box) return;
      box.addEventListener("change", function () {
        fs.classList.toggle("factor--off", !box.checked);
        var details = fs.querySelector(".commute-details");
        var hint = fs.querySelector(".factor-hint");
        if (details) {
          details.hidden = !box.checked;
          if (hint) hint.hidden = box.checked;
          if (box.checked) details.querySelector('input[name="destination_postal"]').focus();
        }
      });
    });
  }

  // Where to Live setup: on every change, POST the form (minus Commute) to /live/check
  // and show which factors would be dropped, before the user submits.
  function initLiveCheck() {
    var form = document.getElementById("live-form");
    if (!form) return;
    var warnings = document.getElementById("warnings");
    var checkUrl = form.getAttribute("data-check-url");
    form.addEventListener("change", function () {
      var data = new FormData(form);
      ["destination_postal", "mode", "include_commute", "weight_commute"].forEach(function (k) {
        data.delete(k);
      });
      fetch(checkUrl, { method: "POST", body: data })
        .then(function (r) { return r.json(); })
        .then(function (j) {
          warnings.innerHTML = "";
          j.warnings.forEach(function (w) {
            var p = document.createElement("p");
            p.className = "note note--warning";
            p.setAttribute("role", "alert");
            p.textContent = w;         // textContent: never interpreted as markup
            warnings.appendChild(p);
          });
        });
    });
  }

  // Where to Live setup: choose neighbourhoods by clicking a 3D map instead of reading
  // 32 checkboxes. The checkboxes remain the form's state and are still what gets
  // posted; this only drives them. If MapLibre, WebGL or the polygon fetch fails, the
  // list stays on screen and nothing is lost.
  //
  // MapLibre rather than Mapbox: no access token, and it is vendored beside Leaflet, so
  // a clean clone and the offline rehearsal both still work. With no network the basemap
  // tiles simply do not arrive and the towns draw on blank, exactly as Leaflet degrades.
  function initAreaPicker() {
    var root = document.getElementById("area-picker");
    if (!root || typeof maplibregl === "undefined") return;
    // supported() exists in some MapLibre versions and not others; when it is missing,
    // a failing Map constructor is caught below and the checkbox list simply stays.
    if (typeof maplibregl.supported === "function" && !maplibregl.supported()) return;
    var mapEl = document.getElementById("area-map");
    var bar = document.getElementById("picker-bar");
    var fallback = document.getElementById("picker-fallback");
    var countEl = document.getElementById("picker-count");
    var chosenEl = document.getElementById("picker-chosen");
    var tiltBtn = document.getElementById("picker-tilt");
    var hint = document.getElementById("picker-hint");
    var form = document.getElementById("live-form");
    var max = parseInt(root.getAttribute("data-max"), 10) || 4;
    var min = parseInt(root.getAttribute("data-min"), 10) || 2;
    var boxes = {};
    root.querySelectorAll('input[name="areas"]').forEach(function (b) { boxes[b.value] = b; });

    fetch(root.getAttribute("data-areas-url")).then(function (r) {
      if (!r.ok) throw new Error("HTTP " + r.status);
      return r.json();
    }).then(function (geojson) {
      build(geojson);
    }).catch(function () {
      // No polygons, no WebGL context, or MapLibre threw: the checkbox list is still
      // on screen and still the form's state, so the page keeps working untouched.
      mapEl.hidden = true;
      bar.hidden = true;
      if (fallback) fallback.open = true;
    });

    function build(geojson) {
      mapEl.hidden = false;
      bar.hidden = false;
      fallback.open = false;
      fallback.querySelector("summary").textContent = "Or choose from a list";

      var byKey = {};
      geojson.features.forEach(function (f) { byKey[f.properties.key] = f; });

      var map = new maplibregl.Map({
        container: mapEl,
        style: {
          version: 8,
          // No glyphs and no symbol layers: nothing here needs a font from the network.
          sources: {
            osm: {
              type: "raster", tileSize: 256, maxzoom: 19,
              tiles: ["https://a.tile.openstreetmap.org/{z}/{x}/{y}.png",
                      "https://b.tile.openstreetmap.org/{z}/{x}/{y}.png",
                      "https://c.tile.openstreetmap.org/{z}/{x}/{y}.png"],
              attribution: "&copy; OpenStreetMap contributors"
            },
            areas: { type: "geojson", data: geojson }
          },
          layers: [
            { id: "canvas", type: "background", paint: { "background-color": "#f7f6f3" } },
            // Washed right out: the basemap is for orientation, the towns are the subject.
            { id: "basemap", type: "raster", source: "osm",
              paint: { "raster-opacity": 0.32, "raster-saturation": -0.9,
                       "raster-contrast": -0.25 } },
            { id: "areas-3d", type: "fill-extrusion", source: "areas", paint: {
                "fill-extrusion-color": [
                  "case",
                  ["boolean", ["feature-state", "selected"], false], "#1f1f1d",
                  ["boolean", ["feature-state", "hover"], false], "#8a887f",
                  "#b4b2a9"
                ],
                // Height is the number of flats, so the bigger towns stand taller.
                // The floor keeps Changi and Downtown Core clickable rather than flat.
                "fill-extrusion-height": ["max", 700, ["*", ["get", "flats"], 0.045]],
                "fill-extrusion-opacity": 0.95,
                "fill-extrusion-vertical-gradient": true
              } },
            { id: "areas-edge", type: "line", source: "areas",
              paint: { "line-color": "#ffffff", "line-width": 1, "line-opacity": 0.5 } }
          ]
        },
        center: [103.82, 1.352], zoom: 10.2, pitch: 0, bearing: 0,
        attributionControl: { compact: true },
        // The page scroll drives the tilt, so the wheel must not also zoom the map.
        scrollZoom: false
      });
      map.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), "top-right");

      // A tooltip, not a popup: no close button, follows the pointer, never clickable.
      var tip = new maplibregl.Popup({ closeButton: false, closeOnClick: false,
                                       className: "picker-tip", offset: 10 });
      var hovered = null;
      map.on("load", function () {
        geojson.features.forEach(function (f) {
          if (boxes[f.properties.key] && boxes[f.properties.key].checked) {
            map.setFeatureState({ source: "areas", id: f.id }, { selected: true });
          }
        });
        map.fitBounds(bounds(geojson), { padding: 28, duration: 0 });
        redraw();
      });

      map.on("mousemove", "areas-3d", function (e) {
        var f = e.features[0];
        if (hovered !== null && hovered !== f.id) {
          map.setFeatureState({ source: "areas", id: hovered }, { hover: false });
        }
        hovered = f.id;
        map.setFeatureState({ source: "areas", id: hovered }, { hover: true });
        map.getCanvas().style.cursor = "pointer";
        tip.setLngLat(e.lngLat).setText(f.properties.name + " — " + f.properties.flats_text)
           .addTo(map);
      });

      map.on("mouseleave", "areas-3d", function () {
        if (hovered !== null) map.setFeatureState({ source: "areas", id: hovered }, { hover: false });
        hovered = null;
        map.getCanvas().style.cursor = "";
        tip.remove();
      });

      map.on("click", "areas-3d", function (e) {
        toggle(e.features[0].properties.key, e.features[0].id);
      });

      function toggle(key, id) {
        var box = boxes[key];
        if (!box) return;
        if (!box.checked && chosenKeys().length >= max) {
          flash("Choose at most " + max + ". Remove one first.");
          return;
        }
        box.checked = !box.checked;
        map.setFeatureState({ source: "areas", id: id }, { selected: box.checked });
        redraw();
        // Let the existing selection-time check re-run against the new selection.
        if (form) form.dispatchEvent(new Event("change", { bubbles: true }));
      }

      function chosenKeys() {
        return Object.keys(boxes).filter(function (k) { return boxes[k].checked; });
      }

      function redraw() {
        var keys = chosenKeys();
        countEl.textContent = keys.length + " of " + min + "–" + max + " chosen";
        countEl.setAttribute("data-state",
          keys.length >= min && keys.length <= max ? "ready" : "");
        chosenEl.textContent = "";
        keys.forEach(function (k) {
          var tag = document.createElement("span");
          tag.className = "chosen-tag";
          // textContent throughout: area names come from the snapshot, but the habit
          // is the point -- nothing on this page is ever inserted as markup.
          tag.textContent = byKey[k] ? byKey[k].properties.name : k;
          var x = document.createElement("button");
          x.type = "button";
          x.setAttribute("aria-label", "Remove " + tag.textContent);
          x.textContent = "×";
          x.addEventListener("click", function () {
            toggle(k, byKey[k] ? byKey[k].id : null);
          });
          tag.appendChild(x);
          chosenEl.appendChild(tag);
        });
      }

      function flash(message) {
        countEl.textContent = message;
        countEl.setAttribute("data-state", "over");
        setTimeout(redraw, 2200);
      }

      // ---- flat to 3D on scroll ----
      // A scroll-linked camera needs the scroll offset itself, so unlike the fade-ins
      // this cannot be an IntersectionObserver. The listener is passive and coalesced
      // into one rAF per frame, and it stops as soon as the user takes the camera over.
      var manual = false;
      var ticking = false;
      var MAX_PITCH = 55;

      // Driven by how far down the page they are, not by where the map sits in the
      // viewport: the map is near the top, so a viewport-relative measure would start
      // it already tilted. This way it is flat when the page loads and rises into 3D
      // as they scroll, which is the behaviour the control promises.
      function applyScrollTilt() {
        ticking = false;
        if (manual) return;
        var vh = window.innerHeight || 800;
        var y = window.pageYOffset || document.documentElement.scrollTop || 0;
        // A short ramp on purpose: the tilt has to finish while the map is still mostly
        // on screen, not after it has scrolled away.
        var progress = Math.max(0, Math.min(1, y / (vh * 0.28)));
        map.jumpTo({ pitch: progress * MAX_PITCH, bearing: progress * -16 });
        setTiltLabel(progress > 0.5);
        if (y > 24 && hint && !hint.hidden) hint.hidden = true;
      }

      function onScroll() {
        if (ticking) return;
        ticking = true;
        window.requestAnimationFrame(applyScrollTilt);
      }

      function setTiltLabel(on) {
        tiltBtn.textContent = on ? "Flat" : "3D";
        tiltBtn.setAttribute("aria-pressed", on ? "true" : "false");
      }

      tiltBtn.addEventListener("click", function () {
        manual = true;                       // the camera is theirs from here on
        if (hint) hint.hidden = true;
        var on = map.getPitch() < MAX_PITCH / 2;
        map.easeTo({ pitch: on ? MAX_PITCH : 0, bearing: on ? -16 : 0, duration: 600 });
        setTiltLabel(on);
      });

      var reduced = window.matchMedia
                 && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      if (reduced) {
        manual = true;                       // only the button tilts the map
        if (hint) hint.textContent = "Click a town to compare it";
      } else {
        window.addEventListener("scroll", onScroll, { passive: true });
        applyScrollTilt();
      }
    }

    function bounds(geojson) {
      var b = new maplibregl.LngLatBounds();
      geojson.features.forEach(function (f) {
        var polys = f.geometry.type === "Polygon" ? [f.geometry.coordinates]
                                                  : f.geometry.coordinates;
        polys.forEach(function (rings) {
          rings[0].forEach(function (c) { b.extend(c); });
        });
      });
      return b;
    }
  }

  // The weight sliders. WebKit has no way to style the part of a track the thumb has
  // already passed, so the fill is painted as a gradient and the stop position is kept
  // in --fill. Firefox has ::-moz-range-progress and needs none of this, but setting
  // the variable anyway costs nothing.
  function initWeightSliders() {
    document.querySelectorAll(".weight-slider").forEach(function (slider) {
      var out = slider.parentNode.querySelector(".weight-value");
      function sync() {
        var min = Number(slider.min || 0), max = Number(slider.max || 100);
        var pct = max === min ? 0 : ((Number(slider.value) - min) / (max - min)) * 100;
        slider.style.setProperty("--fill", pct + "%");
        if (out) out.textContent = slider.value;
      }
      slider.addEventListener("input", sync);
      sync();
    });
  }

  // Where to Lepak: pick a category from a ring of eight instead of reading eight
  // checkboxes, and only then show When, Travel by, At most and the starting point.
  // The checkboxes stay the form's state and are only driven from here, so the POST
  // contract is untouched; with no JS the wheel never appears and the plain checkbox
  // list plus the whole form is what you get.
  function initCategoryWheel() {
    var root = document.getElementById("cat-wheel");
    if (!root) return;
    var wheel = root.querySelector(".wheel");
    var fallback = document.getElementById("wheel-fallback");
    var hub = document.getElementById("wheel-hub");
    var rest = document.getElementById("lepak-rest");
    var segs = Array.prototype.slice.call(root.querySelectorAll(".wheel-seg"));
    var max = parseInt(root.getAttribute("data-max"), 10) || segs.length;
    var allButton = document.getElementById("wheel-all");
    if (!wheel || !segs.length) return;
    var boxes = {};
    root.querySelectorAll('input[name="categories"]').forEach(function (b) {
      boxes[b.value] = b;
    });

    wheel.hidden = false;
    fallback.hidden = true;
    if (allButton) allButton.parentNode.hidden = false;

    function chosen() {
      return Object.keys(boxes).filter(function (k) { return boxes[k].checked; });
    }

    var message = null;

    function redraw() {
      var picked = chosen();
      segs.forEach(function (seg) {
        var on = !!(boxes[seg.getAttribute("data-value")] || {}).checked;
        seg.setAttribute("aria-pressed", on ? "true" : "false");
        seg.classList.toggle("is-blocked", !on && picked.length >= max);
      });
      if (message) {
        hub.textContent = message;
      } else if (!picked.length) {
        hub.innerHTML = "";
        hub.appendChild(document.createTextNode("What do you feel like?"));
      } else {
        hub.innerHTML = "";
        var n = document.createElement("strong");
        n.textContent = picked.length;
        hub.appendChild(n);
        hub.appendChild(document.createTextNode(
          picked.length === 1 ? "category chosen" : "categories chosen"));
      }
      if (allButton) {
        allButton.textContent = picked.length === segs.length ? "Clear" : "All categories";
      }
      // The rest of the search only means anything once there is something to search
      // for, so it stays out of the way until then.
      var show = picked.length > 0;
      if (show && rest.hidden) {
        rest.hidden = false;
        rest.classList.add("is-revealed");
      } else if (!show) {
        rest.hidden = true;
        rest.classList.remove("is-revealed");
      }
    }

    function flash(text) {
      message = text;
      redraw();
      setTimeout(function () { message = null; redraw(); }, 1800);
    }

    // Every category in one click (DECISIONS.md section 32), or none again.
    if (allButton) {
      allButton.addEventListener("click", function () {
        var all = chosen().length !== segs.length;
        segs.forEach(function (seg) {
          var box = boxes[seg.getAttribute("data-value")];
          if (box) box.checked = all;
        });
        redraw();
      });
    }

    segs.forEach(function (seg) {
      seg.addEventListener("click", function () {
        var box = boxes[seg.getAttribute("data-value")];
        if (!box) return;
        if (!box.checked && chosen().length >= max) {
          flash("Up to " + max + ". Unpick one first.");
          return;
        }
        box.checked = !box.checked;
        redraw();
      });
    });

    redraw();
  }

  // A waiting orb for the two submits that genuinely take seconds: the Lepak search
  // routes up to 50 events through OneMap, and Where to Live calls it per area when
  // Commute is on. A form opts in with data-loading-stages, a JSON array of
  // [delay_ms, text] written in its own template.
  //
  // The stages are elapsed-time cues, not measured progress: the browser is doing a
  // plain form POST and the server reports nothing back until it redirects, so there
  // is no real percentage to show. They name the phases the request actually goes
  // through, in the order it goes through them, and deliberately stop short of a
  // progress bar, which would claim a precision we do not have.
  function initLoadingOverlay() {
    var overlay = document.getElementById("page-loader");
    if (!overlay) return;
    var stateEl = document.getElementById("loader-state");
    var slowEl = document.getElementById("loader-slow");
    var timers = [];
    var shown = false;

    function hide() {
      timers.forEach(clearTimeout);
      timers = [];
      shown = false;
      overlay.hidden = true;
      overlay.classList.remove("is-done");
      if (slowEl) slowEl.hidden = true;
      document.querySelectorAll("[data-loading-stages] [type=submit][disabled]")
        .forEach(function (b) { b.disabled = false; });
    }

    // Where to Live with Commute off answers from the local snapshot in milliseconds.
    // Raising the overlay instantly would make those submits flash a spinner that is
    // gone before it can be read, which looks broken. Nothing appears for this long,
    // so a fast submit shows no overlay at all and only a genuinely slow one does.
    var APPEAR_AFTER_MS = 320;

    function show(form) {
      var stages;
      try { stages = JSON.parse(form.getAttribute("data-loading-stages")); }
      catch (e) { return; }
      if (!stages || !stages.length) return;
      shown = true;
      timers.push(setTimeout(function () {
        stateEl.textContent = stages[0][1];
        overlay.hidden = false;
      }, APPEAR_AFTER_MS));
      stages.slice(1).forEach(function (stage) {
        timers.push(setTimeout(function () { stateEl.textContent = stage[1]; },
                               stage[0] + APPEAR_AFTER_MS));
      });
      // Past this the wait is abnormal. Say so plainly rather than inventing another
      // reassuring stage: the p90 for a Lepak search is about 6 s.
      timers.push(setTimeout(function () { if (slowEl) slowEl.hidden = false; }, 12000));
      // Last resort. If the navigation never happens -- a dropped connection, a
      // request that dies silently -- give the page back rather than trapping the
      // user behind an overlay they cannot dismiss.
      timers.push(setTimeout(function () {
        hide();
      }, 60000));
    }

    document.querySelectorAll("form[data-loading-stages]").forEach(function (form) {
      form.addEventListener("submit", function () {
        // Only fires once the browser's own validation has passed, so an invalid form
        // never raises the overlay over the error it is about to show.
        if (shown) return;
        show(form);
        var button = form.querySelector("[type=submit]");
        if (button) button.disabled = true;      // one search per click
      });
    });

    // The new page replaces this one, so the overlay normally dies with it. Two cases
    // where it does not: a back-navigation restoring this page from the bfcache with
    // the overlay still up, and a submit the browser cancelled (a download, a refused
    // navigation), which fires pagehide without ever leaving.
    window.addEventListener("pageshow", function (e) { if (e.persisted) hide(); });
    window.addEventListener("pagehide", function () {
      if (!shown) return;
      // The response has arrived and the next page is about to paint. The orbits stop
      // and the core opens out -- a brief settle rather than another busy frame.
      timers.forEach(clearTimeout);
      overlay.classList.add("is-done");
      if (slowEl) slowEl.hidden = true;
      stateEl.textContent = "Ready";
    });
  }

  // Blocks fade up as they come into view. The hooks are added here rather than in the
  // templates so the markup degrades to plain visible HTML without JS -- and because
  // the event card must stay a bare <article> (tests count that literal string).
  function initReveal() {
    var cards = document.querySelectorAll(".event-cards article");
    cards.forEach(function (el, i) {
      el.setAttribute("data-reveal", "");
      el.style.setProperty("--index", i % 9);     // restart the cascade each row-ish
    });
    var targets = document.querySelectorAll("[data-reveal]");
    if (!targets.length) return;
    var reduced = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduced || typeof IntersectionObserver === "undefined") {
      targets.forEach(function (el) { el.classList.add("is-in"); });
      return;
    }
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (!entry.isIntersecting) return;
        entry.target.classList.add("is-in");
        io.unobserve(entry.target);               // enter once, never replay
      });
    }, { rootMargin: "0px 0px -8% 0px", threshold: 0.05 });
    targets.forEach(function (el) { io.observe(el); });
  }

  document.addEventListener("DOMContentLoaded", function () {
    initMap();
    initChart();
    initDialogs();
    initGeolocation();
    initFactorToggles();
    initLiveCheck();
    initAreaPicker();
    initCategoryWheel();
    initWeightSliders();
    initLoadingOverlay();
    initReveal();
  });
})();
