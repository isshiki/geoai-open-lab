import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from station_access_aging_walking_rules import decisions, foot_scope, audit


class WalkingRulesTests(unittest.TestCase):
    def test_later_matching_rule_overrides_blanket_denial(self):
        rules = [{'access_type': 'denied'},
                 {'access_type': 'allowed', 'when': {'mode': ['foot']}}]
        self.assertEqual(decisions(rules, .5, 'forward'), 'allowed')
        self.assertEqual(decisions(list(reversed(rules)), .5, 'forward'), 'denied')

    def test_mode_free_heading_is_not_assumed_motor_only(self):
        rules = [{'access_type': 'denied', 'when': {'heading': 'backward'}}]
        self.assertEqual(decisions(rules, .5, 'backward'), 'denied')
        self.assertEqual(decisions(rules, .5, 'forward'), 'default_required')

    def test_unknown_conditions_and_false_conjunct(self):
        rules = [{'access_type': 'allowed', 'when': {'recognized': ['as_private']}}]
        self.assertEqual(decisions(rules, .5, 'forward'), 'conditional_unresolved')
        self.assertFalse(foot_scope({'when': {'mode': ['hgv'], 'during': 'unknown'}}, 'forward'))
        self.assertIsNone(foot_scope({'when': {'mode': ['future_mode']}}, 'forward'))
        self.assertEqual(decisions(rules + [{'access_type': 'denied'}], .5, 'forward'), 'denied')

    def test_partial_rules_and_no_implicit_permissions(self):
        rule = {'access_type': 'denied', 'between': [.3, .7]}
        self.assertEqual(decisions([rule], .2, 'forward'), 'default_required')
        self.assertEqual(decisions([rule], .5, 'forward'), 'denied')
        with self.assertRaises(ValueError):
            decisions([dict(rule, between=[.7, .3])], .5, 'forward')
        result = audit([{'class': 'footway', 'access_restrictions': [rule]}])
        self.assertEqual(result['direction_intervals'], {'default_required': 4, 'denied': 2})

    def test_transition_audit_preserves_multistep_and_mode_scope(self):
        transitions = [
            {'sequence': [{}, {}], 'when': {'heading': 'forward'}},
            {'sequence': [{}], 'when': {'mode': ['motor_vehicle']}},
            {'sequence': [{}], 'when': {'during': 'Mo-Fr'}}]
        result = audit([{'class': 'residential', 'prohibited_transitions': transitions}])
        self.assertEqual(result['counts']['transition_rules_multi_step'], 1)
        self.assertEqual(result['transition_scope_counts'], {
            'conditional_unresolved': 1, 'not_foot': 1, 'potentially_applies_to_foot': 1})


if __name__ == '__main__':
    unittest.main()
