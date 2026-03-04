import { Stack } from 'expo-router';
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
          <Stack.Screen name="(tabs)" />
          <Stack.Screen name="onboarding" />
          <Stack.Screen name="workout-questionnaire" options={{ presentation: 'modal' }} />
          <Stack.Screen name="meal-questionnaire" options={{ presentation: 'modal' }} />
          <Stack.Screen name="workout-detail" />
          <Stack.Screen name="meal-detail" />
          <Stack.Screen name="food-log" />
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