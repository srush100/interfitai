import * as Notifications from 'expo-notifications';
import * as Device from 'expo-device';
import { Platform } from 'react-native';
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

export interface WorkoutReminder {
  id: string;
  dayOfWeek: number; // 0 = Sunday, 1 = Monday, etc.
  hour: number;
  minute: number;
  enabled: boolean;
}

export async function registerForPushNotificationsAsync(): Promise<string | null> {
  let token: string | null = null;

  if (Platform.OS === 'android') {
    await Notifications.setNotificationChannelAsync('workout-reminders', {
      name: 'Workout Reminders',
      importance: Notifications.AndroidImportance.HIGH,
      vibrationPattern: [0, 250, 250, 250],
      lightColor: '#FFD700',
    });
  }

  if (Device.isDevice) {
    const { status: existingStatus } = await Notifications.getPermissionsAsync();
    let finalStatus = existingStatus;
    
    if (existingStatus !== 'granted') {
      const { status } = await Notifications.requestPermissionsAsync();
      finalStatus = status;
    }
    
    if (finalStatus !== 'granted') {
      console.log('Failed to get push token for notifications');
      return null;
    }
    
    try {
      const tokenData = await Notifications.getExpoPushTokenAsync({
        projectId: 'your-project-id', // This would be your actual Expo project ID
      });
      token = tokenData.data;
    } catch (e) {
      console.log('Error getting push token:', e);
    }
  } else {
    console.log('Must use physical device for Push Notifications');
  }

  return token;
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
    };

    const notificationId = await Notifications.scheduleNotificationAsync({
      content: {
        title: "Time to Train! 💪",
        body: "Your workout is waiting. Let's crush it today!",
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
    const scheduled = await Notifications.getAllScheduledNotificationsAsync();
    const toCancel = scheduled.find(n => n.identifier.includes(reminderId));
    if (toCancel) {
      await Notifications.cancelScheduledNotificationAsync(toCancel.identifier);
    }
  } catch (error) {
    console.error('Error canceling reminder:', error);
  }
}

export async function saveReminders(reminders: WorkoutReminder[]): Promise<void> {
  try {
    await AsyncStorage.setItem(REMINDER_STORAGE_KEY, JSON.stringify(reminders));
    
    // Reschedule all enabled reminders
    for (const reminder of reminders) {
      await scheduleWorkoutReminder(reminder);
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
  
  // Default reminders (Mon, Wed, Fri at 7am)
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

export async function cancelAllReminders(): Promise<void> {
  await Notifications.cancelAllScheduledNotificationsAsync();
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
