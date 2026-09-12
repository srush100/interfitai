# InterFitAI Test Credentials

## Primary Test User (SDK 57 fork — WORKING, verified via /api/auth/login)
- **email**: `sdk57tester@example.com`
- **password**: `Test1234!`
- **user_id**: `2663e0c4-d8b9-4feb-b42a-8b055631ea25`
- **subscription_status**: free

## Test User
- **user_id**: `cbd82a69-3a37-48c2-88e8-0fe95081fa4b`
- **name**: Test User
- **email**: testuser@example.com (may vary by fork — check DB)
- **Note**: DB resets on fork. Create profile if not present.

## Admin User
- **email**: sebastianrush5@gmail.com
- **Note**: This email is hardcoded in the admin allow-list in server.py

## Test Workout (latest fork)
- **workout_id**: `2d58d2e4-178c-4627-ad56-dee8bbc2d36b`
- **Note**: Workout IDs change per fork; fetch via GET /api/workouts/{user_id}

## App URL
- **Web Preview**: https://nutrition-debug-1.preview.emergentagent.com
- **Backend API**: https://nutrition-debug-1.preview.emergentagent.com/api/
