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
    var layer = L.geoJSON(data, { style: styleForFeature }).bindTooltip(tooltipFor).addTo(map);
    try {
      var bounds = layer.getBounds();
      if (bounds.isValid()) map.fitBounds(bounds, { padding: [16, 16] });
      else throw new Error("empty bounds");
    } catch (e) {
      map.setView([1.3521, 103.8198], 12);   // Singapore, roughly centred
    }
  }

  // The breakdown modal's radar chart. Built lazily, the first time its dialog opens,
  // so a <dialog> that starts closed never tries to size a canvas with zero width.
  function initChart() {
    var canvas = document.getElementById("breakdown-chart");
    var data = readJSON("chart-data");
    if (!canvas || !data || typeof Chart === "undefined") return;
    var rendered = false;
    var render = function () {
      if (rendered) return;
      rendered = true;
      var palette = ["#1d6f5c", "#c9622b", "#4472c4", "#a238a3", "#b8860b", "#2e8b8b"];
      new Chart(canvas, {
        type: "radar",
        data: {
          labels: data.labels,
          datasets: data.datasets.map(function (d, i) {
            var c = palette[i % palette.length];
            return { label: d.label, data: d.data, borderColor: c,
                     backgroundColor: c + "33", pointBackgroundColor: c };
          })
        },
        options: { responsive: true, scales: { r: { min: 0, max: 10, ticks: { stepSize: 2 } } } }
      });
    };
    var dialog = canvas.closest("dialog");
    var opener = dialog && document.querySelector('[data-open-dialog="' + dialog.id + '"]');
    if (opener) opener.addEventListener("click", render);
    else render();
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
    initLiveCheck();
  });
})();
