import json
import tempfile
import unittest
from pathlib import Path

from tools.build_deplao_workflows import build_intake, build_publisher, validate_graph, write_private


class WorkflowTests(unittest.TestCase):
    def test_media_graph_gates_paths_part_ids_receipts_and_separate_branches(self):
        graph=build_publisher('test-bridge-key-123456','303','404',policy_validated=True,binding_verified=True,version=2)
        nodes={n['label']:n for n in graph['nodes']}
        self.assertEqual(nodes['SendPhoto']['type'],'zalo.sendImage')
        self.assertFalse(nodes['SendPhoto']['config']['continueOnError'])
        self.assertEqual(nodes['SendPhoto']['config']['filePath'],'{{ $node.Claim.data.image_path }}')
        self.assertIn('X-Publisher-Version',nodes['Claim']['config']['headers'])
        self.assertIn('part_id',nodes['PhotoAck']['config']['body'])
        self.assertEqual(nodes['ValidPart']['config']['right'],'^[a-f0-9]{32}$')
        self.assertEqual(nodes['PhotoReceipt']['config']['right'],'^[0-9]{1,100}$')
        self.assertEqual(nodes['SafePath']['config']['operator'],'regex')
        validate_graph(graph)

    def test_live_graph_generation_requires_verified_strict_account_binding(self):
        with self.assertRaises(ValueError):
            build_intake('test-intake-key-123456','303','202')
        with self.assertRaises(ValueError):
            build_publisher('test-bridge-key-123456','303','404',policy_validated=True)

    def test_intake_uses_raw_text_metadata_headers_and_original_private_thread(self):
        graph=build_intake('test-intake-key-123456', '303', '202',binding_verified=True)
        validate_graph(graph)
        nodes={n['label']:n for n in graph['nodes']}
        self.assertEqual(nodes['ReceivePrivate']['config']['threadType'],'0')
        self.assertTrue(nodes['ReceivePrivate']['config']['ignoreOwn'])
        self.assertEqual(nodes['Intake']['config']['body'],'NM-TEXT:\n{{ $trigger.content }}')
        headers=json.loads(nodes['Intake']['config']['headers'])
        self.assertEqual(headers['X-Zalo-Message'],'{{ $trigger.msgId }}')
        self.assertEqual(headers['X-Zalo-Sender'],'{{ $trigger.fromId }}')
        self.assertEqual(nodes['PrivateReply']['config']['threadId'],'{{ $trigger.threadId }}')
        self.assertNotIn('test-intake-key-123456',nodes['Intake']['config']['url'])

    def test_publisher_pins_account_group_receipt_and_real_mode(self):
        with self.assertRaises(ValueError):
            build_publisher('test-bridge-key-123456','303','404',binding_verified=True)
        graph=build_publisher('test-bridge-key-123456','303','404',policy_validated=True,binding_verified=True)
        validate_graph(graph)
        nodes={n['label']:n for n in graph['nodes']}
        self.assertEqual(nodes['SendGroup']['config']['threadId'],'404')
        self.assertEqual(nodes['SendGroup']['config']['threadType'],'1')
        self.assertFalse(nodes['SendGroup']['config']['continueOnError'])
        self.assertEqual(nodes['AccountOK']['config']['left'],'{{ $pageId }}')
        self.assertEqual(nodes['Receipt']['config']['operator'],'regex')
        self.assertEqual(nodes['Receipt']['config']['right'],'^[0-9]{1,100}$')
        self.assertIn('/deliveries/claim',nodes['Claim']['config']['url'])
        self.assertIn('"transport_mode": "deplao"',nodes['Ack']['config']['body'])
        self.assertEqual(nodes['Schedule']['config']['cronExpression'],'*/20 * * * * *')

    def test_validation_rejects_unsupported_fields_dangling_edges_and_template_refs(self):
        graph=build_intake('test-intake-key-123456','303','202',binding_verified=True)
        graph['nodes'][0]['config']['unsupported']='invented'
        with self.assertRaises(ValueError): validate_graph(graph)
        graph=build_intake('test-intake-key-123456','303','202',binding_verified=True)
        graph['edges'][0]['target']='missing'
        with self.assertRaises(ValueError): validate_graph(graph)
        graph=build_intake('test-intake-key-123456','303','202',binding_verified=True)
        graph['nodes'][-1]['config']['message']='{{ $node.NoSuchNode.reply }}'
        with self.assertRaises(ValueError): validate_graph(graph)

    def test_credentials_only_written_to_private_path_and_not_overwritten(self):
        graph=build_intake('test-intake-key-123456','303','202',binding_verified=True)
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            with self.assertRaises(ValueError): write_private(root,root/'public/workflow.json',graph)
            with self.assertRaises(ValueError): write_private(root,root/'private/../escaped.json',graph)
            write_private(root,root/'private/workflow.json',graph)
            self.assertTrue((root/'private/workflow.json').exists())
            with self.assertRaises(FileExistsError): write_private(root,root/'private/workflow.json',graph)
