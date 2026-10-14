(function () {
  "use strict";

  function readJSON(id) {
    var el = document.getElementById(id);
    if (!el) return null;
    try { return JSON.parse(el.textContent); } catch (e) { return null; }
  }

  function styleForFeature(feature) {
    var kind = feature.properties && feature.properties.kind;
    if (kind === "route") return { color: "#1d6f5c", weight: 4, opacity: 0.85 };
    if (feature.geometry.type === "Polygon" || feature.geometry.type === "MultiPolygon") {
      var rank = (feature.properties && feature.properties.rank) || 1;
      var palette = ["#1d6f5c", "#4f9d86", "#8cc1ac", "#c6e2d6", "#e4f1ed"];
      var color = palette[Math.min(rank - 1, palette.length - 1)];
      return { color: color, weight: 2, fillColor: color, fillOpacity: 0.35 };
    }
    return { color: "#1d6f5c", weight: 2 };
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
                                          fillColor: "#1d6f5c", fillOpacity: 1 });
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
    var palette = ["#1d6f5c", "#c9622b", "#4472c4", "#a238a3", "#b8860b", "#2e8b8b"];
    var chart = null;
    function draw(type) {
      if (chart) chart.destroy();
      var bar = type === "bar";
      chart = new Chart(canvas, {
        type: type,
        data: {
          labels: data.labels,
          datasets: data.datasets.map(function (d, i) {
            var c = palette[i % palette.length];
            return { label: d.label, data: d.data, borderColor: c, pointBackgroundColor: c,
                     backgroundColor: bar ? c : c + "33", borderWidth: bar ? 0 : 2 };
          })
        },
        options: bar
          ? { indexAxis: "y", responsive: true, maintainAspectRatio: false,
              scales: { x: { min: 0, max: 10, ticks: { stepSize: 2 } } } }
          : { responsive: true, maintainAspectRatio: false,
              scales: { r: { min: 0, max: 10, ticks: { stepSize: 2 } } } }
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

  document.addEventListener("DOMContentLoaded", function () {
    initMap();
    initChart();
    initDialogs();
    initGeolocation();
    initFactorToggles();
    initLiveCheck();
  });
})();
