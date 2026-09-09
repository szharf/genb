import unittest
from test_m4_runtime_state import MutableClock, MutableSource, snapshot
from genb_gateway.runtime_state import ControlSnapshotModule, InMemorySnapshotStore, ConfigurationUnavailable


def node_snapshot(version, host="127.0.0.1"):
    value = snapshot(version)
    value.update(schemaVersion="1.1", implementations=[], bindings=[], agents=[{
        "agentId": "python-node", "status": "PUBLISHED", "upstreamRef": f"http://{host}:18001",
        "identityMode": "SIGNED_TOKEN"}], endpoints=[{
        "agentId": "python-node", "instanceId": "instance-python", "nodeId": "node18",
        "host": host, "port": 18001, "scheme": "http"}])
    return value


class MultinodeEndpointTests(unittest.TestCase):
    def test_new_endpoint_applies_without_restart_and_bad_replacement_keeps_previous(self):
        source = MutableSource(snapshot(1))
        module = ControlSnapshotModule(source=source, store=InMemorySnapshotStore(), clock=MutableClock(),
                                       allowed_node_networks=("127.0.0.0/8",))
        module.start()
        source.version = 2; source.value = node_snapshot(2)
        module.refresh(force=True)
        self.assertEqual("http://127.0.0.1:18001", module.resolve("python-node").upstream)
        source.version = 3; source.value = node_snapshot(3, "169.254.169.254")
        with self.assertRaises(ConfigurationUnavailable): module.refresh(force=True)
        self.assertEqual(2, module.current().config_version)

    def test_endpoint_cannot_be_borrowed_by_another_agent_or_downgraded(self):
        source = MutableSource(node_snapshot(2))
        module = ControlSnapshotModule(source=source, store=InMemorySnapshotStore(), clock=MutableClock(),
                                       allowed_node_networks=("127.0.0.0/8",))
        module.start()
        source.version = 3; source.value = node_snapshot(3)
        source.value["agents"][0]["agentId"] = "other-agent"
        with self.assertRaises(ConfigurationUnavailable): module.refresh(force=True)
        source.version = 1; source.value = snapshot(1)
        with self.assertRaises(ConfigurationUnavailable): module.refresh(force=True)
        self.assertEqual(2, module.current().config_version)
