from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from inferforge.config import resolve_config
from inferforge.inventory import build_inventory
from inferforge.routes import discover_routes

FIXTURE = Path(__file__).parent / "fixtures" / "vulnerable_web"


class InventoryAndRouteTests(unittest.TestCase):
    def test_polyglot_inventory_and_routes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            config = resolve_config(FIXTURE, workspace=temporary)
            inventory = build_inventory(config)
            frameworks = {item["name"] for item in inventory.frameworks}
            self.assertIn("nextjs", frameworks)
            self.assertIn("express", frameworks)
            self.assertIn("flask", frameworks)
            self.assertIn("spring", frameworks)

            routes = discover_routes(inventory)
            endpoints = {(method, route.path) for route in routes for method in route.methods}
            self.assertIn(("POST", "/api/proxy"), endpoints)
            self.assertIn(("POST", "/api/delegated"), endpoints)
            self.assertIn(("GET", "/"), endpoints)
            self.assertIn(("ANY", "/api"), endpoints)
            self.assertIn(("GET", "/api/users/[id]"), endpoints)
            self.assertIn(("PATCH", "/accounts/:id"), endpoints)
            self.assertIn(("POST", "/webhook/provider"), endpoints)
            self.assertIn(("GET", "/download/<path:name>"), endpoints)
            self.assertIn(("DELETE", "/admin/accounts/{id}"), endpoints)
            self.assertIn(("GET", "/teams/:id"), endpoints)
            self.assertIn(("ACTION", "action://src/actions/account.ts#changeEmail"), endpoints)
            self.assertIn(("DELETE", "/admin/[id]"), endpoints)
            self.assertIn(("GET", "/internal/metrics"), endpoints)
            self.assertIn(("POST", "/internal/rotate"), endpoints)
            self.assertIn(("GRAPHQL", "graphql://Query/account"), endpoints)
            self.assertIn(("GRAPHQL", "graphql://Mutation/transfer"), endpoints)
            self.assertIn(("ANY", "/projects/<int:project_id>"), endpoints)

    def test_dynamic_parameters_are_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            config = resolve_config(FIXTURE, workspace=temporary)
            routes = discover_routes(build_inventory(config))
            dynamic = {route.path: route.dynamic_parameters for route in routes if route.dynamic_parameters}
            self.assertEqual(dynamic["/api/users/[id]"], ["id"])
            self.assertEqual(dynamic["/accounts/:id"], ["id"])
            self.assertEqual(dynamic["/admin/accounts/{id}"], ["id"])


if __name__ == "__main__":
    unittest.main()
