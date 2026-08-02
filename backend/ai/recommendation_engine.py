from .constraint_engine import ConstraintEngine


class RecommendationEngine:
    @staticmethod
    def recommend(candidates, constraints, scoring_fields=None):
        if not candidates:
            return [], []

        scored = []
        for candidate in candidates:
            score = ConstraintEngine.score_item(candidate, constraints)

            if scoring_fields:
                for field, weight in scoring_fields.items():
                    val = candidate.get(field)
                    if val is not None:
                        try:
                            score += float(val) * weight
                        except (ValueError, TypeError):
                            pass

            scored.append((score, candidate))

        scored.sort(key=lambda x: -x[0])
        recommendations = [c for _, c in scored]
        rejected = []

        hard_constraints = ConstraintEngine.get_hard_constraints(constraints)
        for candidate in recommendations:
            if ConstraintEngine.violates_hard_constraint(candidate, hard_constraints):
                rejected.append(candidate)
                recommendations.remove(candidate)

        return recommendations[:5], rejected

    @staticmethod
    def compare(candidates, constraints, criteria):
        comparisons = []
        for candidate in candidates:
            item = {
                'candidate': candidate,
                'score': ConstraintEngine.score_item(candidate, constraints),
                'criteria_met': {},
            }
            for criterion in criteria:
                item['criteria_met'][criterion] = ConstraintEngine._matches_constraint(
                    candidate,
                    type('Constraint', (), {'category': criterion, 'value': ''})()
                )
            comparisons.append(item)

        comparisons.sort(key=lambda x: -x['score'])
        return comparisons