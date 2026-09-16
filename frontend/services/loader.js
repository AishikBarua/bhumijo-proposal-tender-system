/* Pulls each screen's markup in from its own folder before anything runs.

   The original file had all four screens inline in one 3,946-line document.
   Splitting the markup is what lets one screen be changed without opening
   the others. The HTML itself is unchanged. */

(function () {
  var SCREENS = [
    { id: 'screen-dashboard', src: '/app/pages/dashboard/dashboard.html' },
    { id: 'screen-proposals', src: '/app/pages/proposals/proposals.html' },
    { id: 'screen-clients',   src: '/app/pages/clients/clients.html' },
    { id: 'screen-reports',   src: '/app/pages/reports/reports.html' }
  ];

  // Synchronous on purpose: the screen markup must exist before the page
  // scripts run, because they look elements up by id at load time — exactly
  // as they did when everything was in one file.
  SCREENS.forEach(function (screen) {
    try {
      var request = new XMLHttpRequest();
      request.open('GET', screen.src, false);
      request.send(null);
      if (request.status >= 200 && request.status < 300) {
        var host = document.getElementById(screen.id);
        if (host) { host.outerHTML = request.responseText; }
      } else {
        console.error('could not load ' + screen.src + ' (HTTP ' + request.status + ')');
      }
    } catch (err) {
      console.error('could not load ' + screen.src, err);
    }
  });
})();
