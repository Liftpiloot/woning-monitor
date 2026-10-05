import importlib
import os
import unittest
from unittest.mock import Mock, patch


def make_response(html: str) -> Mock:
    response = Mock()
    response.text = html
    response.raise_for_status.return_value = None
    return response


class MonitorFetchListingsTests(unittest.TestCase):
    def reload_monitor(self, env=None):
        with patch.dict(os.environ, env or {}, clear=True):
            import monitor

            return importlib.reload(monitor)

    def test_default_urls_are_tried_and_deduplicated(self):
        monitor = self.reload_monitor()
        html_huur = """
        <html><body>
          <a href="/nl/aanbod">Aanbod tab</a>
          <a href="/nl/aanbod/huurwoningen">Huur tab</a>
          <div class="card">
            <a href="/nl/woning/unieke-woning-a">Bekijk</a>
            <h5 class="pb-0">Woning A</h5>
          </div>
        </body></html>
        """
        html_aanbod = """
        <html><body>
          <a href="/nl/aanbod/koopwoningen">Koop tab</a>
          <div class="card">
            <a href="/nl/woning/unieke-woning-a">Bekijk opnieuw</a>
            <h5 class="pb-0">Woning A Dubbel</h5>
          </div>
          <div class="card">
            <a href="/nl/woning/unieke-woning-b">Bekijk</a>
            <h5 class="pb-0">Woning B</h5>
          </div>
        </body></html>
        """

        with patch("monitor.requests.get") as mock_get:
            mock_get.side_effect = [make_response(html_huur), make_response(html_aanbod)]
            listings = monitor.fetch_listings()

        self.assertEqual(mock_get.call_count, 2)
        requested_urls = [call.args[0] for call in mock_get.call_args_list]
        self.assertEqual(requested_urls, monitor.DEFAULT_AANBOD_URLS)
        self.assertEqual({item["id"] for item in listings}, {"unieke-woning-a", "unieke-woning-b"})
        self.assertEqual(len(listings), 2)

    def test_fetch_listings_continues_when_first_url_fails(self):
        monitor = self.reload_monitor()
        html_aanbod = """
        <html><body>
          <div class="card">
            <a href="/nl/woning/fallback-woning">Bekijk</a>
            <h5 class="pb-0">Fallback Woning</h5>
          </div>
        </body></html>
        """

        with patch("monitor.requests.get") as mock_get:
            mock_get.side_effect = [
                monitor.requests.RequestException("tab niet bereikbaar"),
                make_response(html_aanbod),
            ]
            listings = monitor.fetch_listings()

        self.assertEqual(mock_get.call_count, 2)
        self.assertEqual([item["id"] for item in listings], ["fallback-woning"])

    def test_explicit_portal_url_stays_primary_configuration(self):
        custom_url = "https://voorbeeld.nl/custom-aanbod"
        monitor = self.reload_monitor({"PORTAL_URL": custom_url})
        html_custom = """
        <html><body>
          <div class="card">
            <a href="/nl/woning/custom-woning">Bekijk</a>
            <h5 class="pb-0">Custom Woning</h5>
          </div>
        </body></html>
        """

        self.assertEqual(monitor.AANBOD_URLS, [custom_url])

        with patch("monitor.requests.get") as mock_get:
            mock_get.return_value = make_response(html_custom)
            listings = monitor.fetch_listings()

        self.assertEqual(mock_get.call_count, 1)
        self.assertEqual(mock_get.call_args.args[0], custom_url)
        self.assertEqual([item["id"] for item in listings], ["custom-woning"])


if __name__ == "__main__":
    unittest.main()
