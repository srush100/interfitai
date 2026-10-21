import * as Notifications from 'expo-notifications';
import * as Device from 'expo-device';
import { Platform } from 'react-native';
import Constants from 'expo-constants';
import AsyncStorage from '@react-native-async-storage/async-storage';

// Configure notification handler
Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowAlert: true,
    shouldPlaySound: true,
    shouldSetBadge: false,
    shouldShowBanner: true,
    shouldShowList: true,
  }),
});

const REMINDER_STORAGE_KEY = '@workout_reminders';
// Every workout reminder is scheduled under this name + its day id, so it can
// be found and cancelled again
const REMINDER_PREFIX = 'workout-reminder-';
const ANDROID_CHANNEL = 'workout-reminders';

export interface WorkoutReminder {
  id: string;
  dayOfWeek: number; // 0 = Sunday, 1 = Monday, etc.
  hour: number;
  minute: number;
  enabled: boolean;
}

// Asks for notification permission if needed. true when reminders can be shown.
export async function ensureNotificationPermission(): Promise<boolean> {
  if (Platform.OS === 'android') {
    await Notifications.setNotificationChannelAsync(ANDROID_CHANNEL, {
      name: 'Workout Reminders',
      importance: Notifications.AndroidImportance.HIGH,
      vibrationPattern: [0, 250, 250, 250],
      lightColor: '#FFD700',
    });
  }
  const { status: existing } = await Notifications.getPermissionsAsync();
  if (existing === 'granted') return true;
  const { status } = await Notifications.requestPermissionsAsync();
  return status === 'granted';
}

// Push token for server-sent notifications. Workout reminders are local and
// don't need it; it's only fetched when the EAS project id is configured.
export async function registerForPushNotificationsAsync(): Promise<string | null> {
  if (!(await ensureNotificationPermission()) || !Device.isDevice) return null;
  const projectId = (Constants.expoConfig as any)?.extra?.eas?.projectId
    || (Constants as any).easConfig?.projectId;
  if (!projectId) return null;
  try {
    return (await Notifications.getExpoPushTokenAsync({ projectId })).data;
  } catch (e) {
    console.log('Error getting push token:', e);
    return null;
  }
}

export async function scheduleWorkoutReminder(reminder: WorkoutReminder): Promise<string | null> {
  try {
    // Cancel existing reminder with same ID first
    await cancelWorkoutReminder(reminder.id);
    
    if (!reminder.enabled) {
      return null;
    }

    const trigger: Notifications.WeeklyTriggerInput = {
      type: Notifications.SchedulableTriggerInputTypes.WEEKLY,
      weekday: reminder.dayOfWeek + 1, // Expo uses 1-7 (Sun=1)
      hour: reminder.hour,
      minute: reminder.minute,
      channelId: ANDROID_CHANNEL,
    };

    const REMINDER_BODIES = [
      "Your workout is waiting. Let's crush it today!",
      "Show up for yourself — your future self will thank you.",
      "Consistency beats intensity. Time to put in the work.",
      "One session closer to your goal. Let's go.",
      "The hardest part is starting. Open the app and begin.",
      "Strong isn't given — it's earned. Today's your day.",
      "Momentum is built one workout at a time. Keep yours going.",
    ];
    const notificationId = await Notifications.scheduleNotificationAsync({
      identifier: `${REMINDER_PREFIX}${reminder.id}`,
      content: {
        title: "Time to Train! 💪",
        body: REMINDER_BODIES[reminder.dayOfWeek % REMINDER_BODIES.length],
        data: { type: 'workout_reminder' },
        sound: 'default',
      },
      trigger,
    });

    return notificationId;
  } catch (error) {
    console.error('Error scheduling reminder:', error);
    return null;
  }
}

export async function cancelWorkoutReminder(reminderId: string): Promise<void> {
  try {
    await Notifications.cancelScheduledNotificationAsync(`${REMINDER_PREFIX}${reminderId}`);
  } catch (error) {
    // nothing scheduled under that name
  }
}

// Every scheduled workout reminder — including unnamed ones left by older app
// builds, which scheduled duplicates without an id
async function cancelAllWorkoutReminders(): Promise<void> {
  const scheduled = await Notifications.getAllScheduledNotificationsAsync();
  for (const n of scheduled) {
    if (n.identifier.startsWith(REMINDER_PREFIX) || (n.content?.data as any)?.type === 'workout_reminder') {
      await Notifications.cancelScheduledNotificationAsync(n.identifier);
    }
  }
}

// Saves the reminders and makes the phone's schedule match them exactly:
// one notification per enabled day, nothing for disabled days.
export async function saveReminders(reminders: WorkoutReminder[]): Promise<void> {
  try {
    await AsyncStorage.setItem(REMINDER_STORAGE_KEY, JSON.stringify(reminders));
    await cancelAllWorkoutReminders();
    for (const reminder of reminders) {
      if (reminder.enabled) await scheduleWorkoutReminder(reminder);
    }
  } catch (error) {
    console.error('Error saving reminders:', error);
  }
}

export async function loadReminders(): Promise<WorkoutReminder[]> {
  try {
    const stored = await AsyncStorage.getItem(REMINDER_STORAGE_KEY);
    if (stored) {
      return JSON.parse(stored);
    }
  } catch (error) {
    console.error('Error loading reminders:', error);
  }
  
  // Default reminders: every day off (weekdays 7am, weekends 9am)
  return [
    { id: 'mon', dayOfWeek: 1, hour: 7, minute: 0, enabled: false },
    { id: 'tue', dayOfWeek: 2, hour: 7, minute: 0, enabled: false },
    { id: 'wed', dayOfWeek: 3, hour: 7, minute: 0, enabled: false },
    { id: 'thu', dayOfWeek: 4, hour: 7, minute: 0, enabled: false },
    { id: 'fri', dayOfWeek: 5, hour: 7, minute: 0, enabled: false },
    { id: 'sat', dayOfWeek: 6, hour: 9, minute: 0, enabled: false },
    { id: 'sun', dayOfWeek: 0, hour: 9, minute: 0, enabled: false },
  ];
}

// Signing out: stop this user's reminders on the phone
export async function cancelAllReminders(): Promise<void> {
  await cancelAllWorkoutReminders();
  await AsyncStorage.removeItem(REMINDER_STORAGE_KEY);
}

// Notification listeners
export function addNotificationReceivedListener(
  callback: (notification: Notifications.Notification) => void
) {
  return Notifications.addNotificationReceivedListener(callback);
}

export function addNotificationResponseReceivedListener(
  callback: (response: Notifications.NotificationResponse) => void
) {
  return Notifications.addNotificationResponseReceivedListener(callback);
}
