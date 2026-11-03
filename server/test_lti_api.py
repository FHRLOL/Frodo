import os
import sys
import json
import time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

SERVER_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.join(SERVER_DIR, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)
if SERVER_DIR not in sys.path:
    sys.path.insert(0, SERVER_DIR)

from fastapi.testclient import TestClient
from main import app
from database import db
from lti.service import compute_oauth1_signature

def test_full_flow():
    client = TestClient(app)

    print("--- 1. Testing Database & Seed ---")
    db.init_db()
    db.seed_db()
    labs = db.get_all_labs()
    assert len(labs) == 3, f"Expected 3 labs, got {len(labs)}"
    print(f"[OK] Labs initialized: {[l['title'] for l in labs]}")

    users = db.list_students()
    assert len(users) >= 1, "Expected at least 1 student"
    print(f"[OK] Students in DB: {[u['name'] for u in users]}")

    print("\n--- 2. Testing LTI Launch (Student) ---")
    student_launch_params = {
        "oauth_consumer_key": "frodo_lti_key",
        "oauth_signature_method": "HMAC-SHA1",
        "oauth_timestamp": str(int(time.time())),
        "oauth_nonce": "test_nonce_student_123",
        "oauth_version": "1.0",
        "lti_message_type": "basic-lti-launch-request",
        "lti_version": "LTI-1p0",
        "user_id": "student_42",
        "roles": "Learner",
        "lis_person_name_full": "Алексей Иванов",
        "lis_person_contact_email_primary": "student_42@university.edu",
        "format": "json"
    }
    # Подпись для http://testserver/lti/launch
    sig = compute_oauth1_signature("POST", "http://testserver/lti/launch", student_launch_params, "frodo_lti_secret")
    student_launch_params["oauth_signature"] = sig

    resp = client.post("/lti/launch", data=student_launch_params, headers={"Accept": "application/json"})
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    student_data = resp.json()
    student_token = student_data["token"]
    assert student_data["user"]["role"] == "student"
    print(f"[OK] Student LTI Launch OK, token: {student_token[:20]}...")

    print("\n--- 3. Testing LTI Launch (Instructor) ---")
    instructor_launch_params = {
        "oauth_consumer_key": "frodo_lti_key",
        "oauth_signature_method": "HMAC-SHA1",
        "oauth_timestamp": str(int(time.time())),
        "oauth_nonce": "test_nonce_instructor_456",
        "oauth_version": "1.0",
        "lti_message_type": "basic-lti-launch-request",
        "lti_version": "LTI-1p0",
        "user_id": "instructor_1",
        "roles": "Instructor",
        "lis_person_name_full": "Проф. Смирнов А.В.",
        "lis_person_contact_email_primary": "prof_smirnov@university.edu",
        "format": "json"
    }
    sig_inst = compute_oauth1_signature("POST", "http://testserver/lti/launch", instructor_launch_params, "frodo_lti_secret")
    instructor_launch_params["oauth_signature"] = sig_inst

    resp = client.post("/lti/launch", data=instructor_launch_params, headers={"Accept": "application/json"})
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    instructor_data = resp.json()
    instructor_token = instructor_data["token"]
    assert instructor_data["user"]["role"] == "instructor"
    print(f"[OK] Instructor LTI Launch OK, token: {instructor_token[:20]}...")

    print("\n--- 4. Testing GET /api/auth/me ---")
    headers_student = {"Authorization": f"Bearer {student_token}"}
    resp = client.get("/api/auth/me", headers=headers_student)
    assert resp.status_code == 200
    me_student = resp.json()
    assert me_student["moodle_user_id"] == "student_42"
    assert me_student["role"] == "student"
    print(f"[OK] Auth me (student): {me_student['name']} ({me_student['role']})")

    headers_instructor = {"Authorization": f"Bearer {instructor_token}"}
    resp = client.get("/api/auth/me", headers=headers_instructor)
    assert resp.status_code == 200
    me_inst = resp.json()
    assert me_inst["role"] == "instructor"
    print(f"[OK] Auth me (instructor): {me_inst['name']} ({me_inst['role']})")

    print("\n--- 5. Testing GET /api/labs ---")
    resp = client.get("/api/labs")
    assert resp.status_code == 200
    all_labs = resp.json()
    assert len(all_labs) == 3
    print(f"[OK] Catalog labs: {len(all_labs)} items")

    print("\n--- 6. Testing GET /api/student/progress ---")
    resp = client.get("/api/student/progress", headers=headers_student)
    assert resp.status_code == 200
    progress = resp.json()
    assert len(progress) == 3
    print(f"[OK] Student progress count: {len(progress)}")
    for item in progress:
        print(f"    Lab {item['order_num']}: {item['title']} -> {item['status']} (Grade: {item['grade']}, can_master: {item['can_master_mode']})")

    print("\n--- 7. Testing RBAC on GET /api/admin/students ---")
    # Студент не должен иметь доступ
    resp = client.get("/api/admin/students", headers=headers_student)
    assert resp.status_code == 403, f"Expected 403 Forbidden for student, got {resp.status_code}"
    print("[OK] Student correctly forbidden (403) from accessing admin students matrix")

    # Преподаватель имеет доступ
    resp = client.get("/api/admin/students", headers=headers_instructor)
    assert resp.status_code == 200, f"Expected 200 for instructor, got {resp.status_code}"
    matrix = resp.json()
    assert len(matrix) >= 1
    print(f"[OK] Instructor accessed student matrix: {len(matrix)} students")

    print("\n--- 8. Testing POST /api/admin/student/progress ---")
    # Попытка студента изменить прогресс -> 403
    student_id = me_student["id"]
    update_payload = {
        "user_id": student_id,
        "lab_id": 2,
        "status": "passed",
        "grade": 95.0
    }
    resp = client.post("/api/admin/student/progress", json=update_payload, headers=headers_student)
    assert resp.status_code == 403
    print("[OK] Student forbidden (403) from updating progress")

    # Преподаватель обновляет прогресс
    resp = client.post("/api/admin/student/progress", json=update_payload, headers=headers_instructor)
    assert resp.status_code == 200
    updated = resp.json()
    assert updated["status"] == "passed"
    assert updated["grade"] == 95.0
    assert updated["can_master_mode"] is True
    print(f"[OK] Instructor successfully updated Lab 2 to passed (grade: {updated['grade']}, can_master: {updated['can_master_mode']})")

    # Проверяем, что у студента обновилось
    resp = client.get("/api/student/progress", headers=headers_student)
    p2 = [x for x in resp.json() if x["lab_id"] == 2][0]
    assert p2["status"] == "passed"
    assert p2["grade"] == 95.0
    print(f"[OK] Student sees updated status for Lab 2: {p2['status']} (can_master: {p2['can_master_mode']})")

    print("\n--- 9. Testing GET /api/admin/unanswered ---")
    # Добавляем вопрос в unanswered_queries для теста
    db.add_unanswered_query(
        question="Какая сложность поиска в словаре Python по алгоритму Big O?",
        user_id=student_id,
        score=0.25,
        reason="Guardrail rejection: below threshold 0.45"
    )
    resp = client.get("/api/admin/unanswered", headers=headers_instructor)
    assert resp.status_code == 200
    unanswered = resp.json()
    assert len(unanswered) >= 1
    print(f"[OK] Gap Analysis unanswered list: {len(unanswered)} items. First: '{unanswered[0]['question']}' (reason: {unanswered[0]['reason']})")

    # Студент не имеет доступа к unanswered
    resp = client.get("/api/admin/unanswered", headers=headers_student)
    assert resp.status_code == 403
    print("[OK] Student forbidden (403) from viewing unanswered questions")

    print("\n================ ALL TESTS PASSED SUCCESSFULLY! ================\n")

if __name__ == "__main__":
    test_full_flow()
