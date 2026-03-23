import React, { useEffect, useState } from 'react';
import { View, Text, StyleSheet, Image, ActivityIndicator } from 'react-native';
import { useRouter } from 'expo-router';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { useUserStore } from '../src/store/userStore';
import { colors } from '../src/theme/colors';

export default function SplashScreen() {
  const router = useRouter();
  const { isOnboarded, profile, loadProfile } = useUserStore();
  const [hasChecked, setHasChecked] = useState(false);
  const [hasEverOnboarded, setHasEverOnboarded] = useState(false);

  useEffect(() => {
    const checkAndLoad = async () => {
      // Check if user has ever created an account
      const everOnboarded = await AsyncStorage.getItem('hasEverOnboarded');
      setHasEverOnboarded(everOnboarded === 'true');
      
      // Load profile
      await loadProfile();
      setHasChecked(true);
    };
    checkAndLoad();
  }, []);

  useEffect(() => {
    if (!hasChecked) return;
    
    const timer = setTimeout(() => {
      if (isOnboarded && profile) {
        // User is logged in - go to main app
        router.replace('/(tabs)');
      } else if (hasEverOnboarded) {
        // User has logged out but had an account before - show login
        router.replace('/login');
      } else {
        // New user - show onboarding
        router.replace('/onboarding');
      }
    }, 1500);

    return () => clearTimeout(timer);
  }, [hasChecked, isOnboarded, profile, hasEverOnboarded]);

  return (
    <View style={styles.container}>
      <View style={styles.logoGlow}>
        <Image
          source={require('../assets/logo-icon-yellow.png')}
          style={styles.logo}
          resizeMode="contain"
        />
      </View>
      <View style={styles.titleContainer}>
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
  logoGlow: {
    width: 120,
    height: 120,
    borderRadius: 60,
    backgroundColor: 'rgba(255, 204, 0, 0.15)',
    borderWidth: 2,
    borderColor: 'rgba(255, 204, 0, 0.3)',
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 20,
  },
  logo: {
    width: 70,
    height: 70,
  },
  titleContainer: {
    flexDirection: 'row',
    alignItems: 'baseline',
  },
  logoText: {
    fontSize: 42,
    fontWeight: '800',
    color: colors.text,
    letterSpacing: 2,
  },
  logoAI: {
    fontSize: 42,
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
