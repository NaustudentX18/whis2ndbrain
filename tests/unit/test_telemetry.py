"""Unit tests for server.telemetry — TelemetryStore and SSEBroker."""

import time
import unittest

from server.telemetry import (
    SSEBroker,
    TelemetrySnapshot,
    TelemetryStore,
    _float_or_none,
    _int_or_none,
)


class TelemetrySnapshotTests(unittest.TestCase):
    def test_empty_snapshot_connection_quality_is_unknown(self):
        s = TelemetrySnapshot()
        self.assertEqual(s.connection_quality(), "unknown")
        self.assertIsNone(s.age_seconds())

    def test_fresh_heartbeat_is_online(self):
        s = TelemetrySnapshot(last_seen_at=time.time())
        self.assertEqual(s.connection_quality(), "online")

    def test_old_heartbeat_is_stale(self):
        s = TelemetrySnapshot(last_seen_at=time.time() - 200)
        self.assertEqual(s.connection_quality(), "stale")

    def test_very_old_heartbeat_is_offline(self):
        s = TelemetrySnapshot(last_seen_at=time.time() - 700)
        self.assertEqual(s.connection_quality(), "offline")

    def test_to_dict_includes_all_fields(self):
        s = TelemetrySnapshot(device_id="pi-001", battery_pct=85.5)
        d = s.to_dict()
        self.assertIn("device_id", d)
        self.assertIn("connection_quality", d)
        self.assertIn("battery_pct", d)
        self.assertEqual(d["device_id"], "pi-001")
        self.assertEqual(d["battery_pct"], 85.5)


class TelemetryStoreTests(unittest.TestCase):
    def test_initial_get_returns_empty_snapshot(self):
        store = TelemetryStore()
        s = store.get()
        self.assertIsNone(s.device_id)
        self.assertIsNone(s.last_seen_at)

    def test_update_records_last_seen(self):
        store = TelemetryStore()
        before = time.time()
        store.update({"device_id": "pi-001", "queue_depth": 3})
        s = store.get()
        self.assertEqual(s.device_id, "pi-001")
        self.assertEqual(s.queue_depth, 3)
        self.assertGreaterEqual(s.last_seen_at, before)

    def test_update_merges_with_previous(self):
        store = TelemetryStore()
        store.update({"device_id": "pi-001"})
        store.update({"battery_pct": 72.0})
        s = store.get()
        self.assertEqual(s.device_id, "pi-001")  # preserved from first update
        self.assertEqual(s.battery_pct, 72.0)

    def test_update_with_empty_dict_still_updates_last_seen(self):
        store = TelemetryStore()
        store.update({})
        s = store.get()
        self.assertIsNotNone(s.last_seen_at)

    def test_update_ignores_invalid_numeric_types(self):
        store = TelemetryStore()
        store.update({"battery_pct": "not-a-number"})
        s = store.get()
        self.assertIsNone(s.battery_pct)


class SSEBrokerTests(unittest.TestCase):
    def test_subscribe_and_publish(self):
        broker = SSEBroker()
        q = broker.subscribe()
        broker.publish("test_event", '{"x":1}')
        msg = q.get_nowait()
        self.assertIn("event: test_event", msg)
        self.assertIn('{"x":1}', msg)

    def test_multiple_subscribers_each_receive_event(self):
        broker = SSEBroker()
        q1 = broker.subscribe()
        q2 = broker.subscribe()
        broker.publish("ping", "{}")
        self.assertFalse(q1.empty())
        self.assertFalse(q2.empty())

    def test_unsubscribe_stops_delivery(self):
        broker = SSEBroker()
        q = broker.subscribe()
        broker.unsubscribe(q)
        broker.publish("ping", "{}")
        self.assertTrue(q.empty())

    def test_close_all_sends_none_sentinel(self):
        broker = SSEBroker()
        q = broker.subscribe()
        broker.close_all()
        msg = q.get_nowait()
        self.assertIsNone(msg)

    def test_double_unsubscribe_is_safe(self):
        broker = SSEBroker()
        q = broker.subscribe()
        broker.unsubscribe(q)
        broker.unsubscribe(q)  # should not raise


class HelperTests(unittest.TestCase):
    def test_float_or_none(self):
        self.assertEqual(_float_or_none(3.14), 3.14)
        self.assertEqual(_float_or_none("2.5"), 2.5)
        self.assertIsNone(_float_or_none(None))
        self.assertIsNone(_float_or_none("bad"))

    def test_int_or_none(self):
        self.assertEqual(_int_or_none(5), 5)
        self.assertEqual(_int_or_none("7"), 7)
        self.assertIsNone(_int_or_none(None))
        self.assertIsNone(_int_or_none("bad"))
