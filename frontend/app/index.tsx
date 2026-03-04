import React, { useEffect } from 'react';
import { View, Text, StyleSheet, Image, ActivityIndicator } from 'react-native';
import { useRouter } from 'expo-router';
import { useUserStore } from '../src/store/userStore';
import { colors } from '../src/theme/colors';

export default function SplashScreen() {
  const router = useRouter();
  const { isOnboarded, profile } = useUserStore();

  useEffect(() => {
    const timer = setTimeout(() => {
      if (isOnboarded && profile) {
        router.replace('/(tabs)');
      } else {
        router.replace('/onboarding');
      }
    }, 2000);

    return () => clearTimeout(timer);
  }, [isOnboarded, profile]);

  return (
    <View style={styles.container}>
      <View style={styles.logoContainer}>
        <Text style={styles.logoText}>INTERFIT</Text>
        <Text style={styles.logoAI}>AI</Text>
      </View>
      <Text style={styles.tagline}>Your AI-Powered Fitness Companion</Text>
      <ActivityIndicator size="large" color={colors.primary} style={styles.loader} />
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
    justifyContent: 'center',
    alignItems: 'center',
    padding: 20,
  },
  logoContainer: {
    flexDirection: 'row',
    alignItems: 'baseline',
  },
  logoText: {
    fontSize: 48,
    fontWeight: '800',
    color: colors.text,
    letterSpacing: 2,
  },
  logoAI: {
    fontSize: 48,
    fontWeight: '800',
    color: colors.primary,
    letterSpacing: 2,
  },
  tagline: {
    fontSize: 16,
    color: colors.textSecondary,
    marginTop: 12,
    letterSpacing: 1,
  },
  loader: {
    marginTop: 40,
  },
});