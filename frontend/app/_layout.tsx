import { Stack, router } from 'expo-router';
import * as Notifications from 'expo-notifications';
import { StatusBar } from 'expo-status-bar';
import { useEffect, useState } from 'react';
import { View, ActivityIndicator, StyleSheet } from 'react-native';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { GestureHandlerRootView } from 'react-native-gesture-handler';
import { useUserStore } from '../src/store/userStore';

export default function RootLayout() {
  const [isReady, setIsReady] = useState(false);
  const loadProfile = useUserStore((state) => state.loadProfile);

  useEffect(() => {
    const init = async () => {
      await loadProfile();
      setIsReady(true);
    };
    init();
  }, []);

  // Tapping a workout reminder ("Time to Train!") opens the Workouts tab — also
  // when the tap started the app (only a tap from the last minute, so an old
  // tap never reopens it on a later launch)
  useEffect(() => {
    if (!isReady) return;
    const open = (r: Notifications.NotificationResponse | null, coldStart = false) => {
      if ((r?.notification.request.content.data as any)?.type !== 'workout_reminder') return;
      if (coldStart && Date.now() - (r?.notification.date || 0) > 60_000) return;
      if (useUserStore.getState().profile) router.push('/(tabs)/workouts');
    };
    Notifications.getLastNotificationResponseAsync().then((r) => open(r, true)).catch(() => {});
    const sub = Notifications.addNotificationResponseReceivedListener((r) => open(r));
    return () => sub.remove();
  }, [isReady]);

  if (!isReady) {
    return (
      <View style={styles.loading}>
        <ActivityIndicator size="large" color="#FFD700" />
      </View>
    );
  }

  return (
    <GestureHandlerRootView style={{ flex: 1 }}>
      <SafeAreaProvider>
        <StatusBar style="light" />
        <Stack
          screenOptions={{
            headerShown: false,
            contentStyle: { backgroundColor: '#121212' },
            animation: 'slide_from_right',
          }}
        >
          <Stack.Screen name="index" />
          <Stack.Screen name="welcome" />
          <Stack.Screen name="login" />
          <Stack.Screen name="forgot-password" />
          <Stack.Screen name="(tabs)" />
          <Stack.Screen name="onboarding" />
          <Stack.Screen name="workout-questionnaire" options={{ presentation: 'modal' }} />
          <Stack.Screen name="meal-questionnaire" options={{ presentation: 'modal' }} />
          <Stack.Screen name="workout-detail" />
          <Stack.Screen name="meal-detail" />
          <Stack.Screen name="food-log" />
          <Stack.Screen name="progress" />
          <Stack.Screen name="subscription" />
          <Stack.Screen name="subscription/success" />
        </Stack>
      </SafeAreaProvider>
    </GestureHandlerRootView>
  );
}

const styles = StyleSheet.create({
  loading: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: '#121212',
  },
});