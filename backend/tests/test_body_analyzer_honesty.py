"""
Body analyser on TestFlight (15 Nov): clear fat gain between the photos, but
the answer was 'very little visible change', 22-25% for both photos and 2/10.
The prompt now puts honesty first (each photo judged on its own, a stated
direction, a score towards the goal), and the answer is checked in code so
the estimates, the direction, the wording and the score can't contradict.
"""
import server

C = server._clean_body_analysis


def test_fat_gain_against_weight_loss_goal_scores_low():
    r = C({"change_direction": "fat_gain", "estimated_progress_score": 6, "areas_improved": ["Chest"],
           "estimated_body_fat_before": "20-23%", "estimated_body_fat_after": "24-27%",
           "overall_assessment": "The after photo shows more body fat.", "analysis_confidence": "medium"}, "weight_loss")
    assert r["estimated_progress_score"] == 1 and r["areas_improved"] == []
    assert r["headline"].startswith("The after photo shows more body fat")


def test_estimates_contradicting_no_change_wording():
    r = C({"change_direction": "no_clear_change", "estimated_progress_score": 4,
           "estimated_body_fat_before": "Estimate: 20-23%", "estimated_body_fat_after": "Estimate: 25-28%",
           "overall_assessment": "Comparing these two photos, there is very little visible change.",
           "analysis_confidence": "medium"}, "weight_loss")
    assert r["change_direction"] == "fat_gain"
    assert r["overall_assessment"].startswith("The after photo shows more body fat")
    assert r["estimated_progress_score"] == 1
    assert r["estimated_body_fat_before"] == "20-23%"           # no doubled 'Estimate:'


def test_real_fat_loss_keeps_its_score():
    r = C({"change_direction": "fat_loss", "estimated_progress_score": 8, "areas_improved": ["Waist"],
           "estimated_body_fat_before": "25-28%", "estimated_body_fat_after": "19-22%",
           "overall_assessment": "The after photo shows clearly less body fat.", "analysis_confidence": "high"}, "weight_loss")
    assert r["estimated_progress_score"] == 8 and r["areas_improved"] == ["Waist"]


def test_weight_gain_given_caps_a_weight_loss_score():
    r = C({"change_direction": "fat_loss", "estimated_progress_score": 7,
           "estimated_body_fat_before": "22-25%", "estimated_body_fat_after": "21-24%",
           "analysis_confidence": "medium"}, "weight_loss", weight_delta=5.0)
    assert r["estimated_progress_score"] <= 3


def test_no_clear_change_never_scores_high():
    r = C({"change_direction": "no_clear_change", "estimated_progress_score": 7,
           "estimated_body_fat_before": "18-21%", "estimated_body_fat_after": "18-21%"}, "maintenance")
    assert r["estimated_progress_score"] <= 3 and r["headline"].startswith("There is no clear change")


def test_not_analysed_stays_zero():
    r = C({"change_direction": "unclear_photos", "estimated_progress_score": 0, "analysis_confidence": "low"}, "weight_loss")
    assert r["estimated_progress_score"] == 0


def test_unknown_direction_and_old_answers_still_work():
    r = C({"estimated_progress_score": 5, "estimated_body_fat_before": "18-21%", "estimated_body_fat_after": "17-20%"})
    assert r["change_direction"] == "" and r["estimated_progress_score"] == 5 and r["headline"] == ""
    r = C({"estimated_progress_score": 6, "estimated_body_fat_before": "18-21%", "estimated_body_fat_after": "23-26%"},
          "weight_loss")
    assert r["change_direction"] == "fat_gain" and r["estimated_progress_score"] == 1


def test_prompt_is_honesty_first():
    import inspect
    src = inspect.getsource(server.analyze_body_progress)
    assert "HONESTY COMES FIRST" in src and "ON ITS OWN" in src and "change_direction" in src
    assert "Be encouraging but HONEST" not in src and "temperature=0.0" in src
