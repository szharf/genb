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
    def test_legacy_target_requires_new_schema_and_independent_network_approval(self):
        value = node_snapshot(2, "10.20.1.47")
        value["schemaVersion"] = "1.2"
        endpoint = value["endpoints"][0]
        endpoint.pop("instanceId")
        endpoint["legacyTargetId"] = "deployment:10"
        source = MutableSource(value)
        module = ControlSnapshotModule(source=source, store=InMemorySnapshotStore(), clock=MutableClock(),
                                       allowed_node_networks=("10.20.1.47/32",))
        module.start()
        self.assertEqual("http://10.20.1.47:18001", module.resolve("python-node").upstream)
        for change in (lambda v: v.update(schemaVersion="1.1"),
                       lambda v: v["endpoints"][0].update(instanceId="fake"),
                       lambda v: v["endpoints"][0].update(legacyTargetId="process:another-agent"),
                       lambda v: v["endpoints"][0].update(host="10.20.1.48")):
            import copy
            source.value = copy.deepcopy(value); source.value["configVersion"] = 3; source.version = 3
            change(source.value)
            with self.assertRaises(ConfigurationUnavailable): module.refresh(force=True)
            self.assertEqual(2, module.current().config_version)

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
