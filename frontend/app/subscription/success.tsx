import React, { useEffect, useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ActivityIndicator,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter, useLocalSearchParams } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { useUserStore } from '../../src/store/userStore';
import { colors } from '../../src/theme/colors';
import api from '../../src/services/api';

export default function SubscriptionSuccess() {
  const router = useRouter();
  const { session_id } = useLocalSearchParams();
  const { loadProfile } = useUserStore();
  const [status, setStatus] = useState<'loading' | 'success' | 'error'>('loading');
  const [attempts, setAttempts] = useState(0);

  useEffect(() => {
    if (session_id) {
      pollPaymentStatus();
    }
  }, [session_id]);

  const pollPaymentStatus = async () => {
    const maxAttempts = 5;
    const pollInterval = 2000;

    if (attempts >= maxAttempts) {
      setStatus('error');
      return;
    }

    try {
      const response = await api.get(`/subscription/status/${session_id}`);
      
      if (response.data.payment_status === 'paid') {
        setStatus('success');
        await loadProfile();
        setTimeout(() => router.replace('/(tabs)'), 2000);
        return;
      } else if (response.data.status === 'expired') {
        setStatus('error');
        return;
      }

      setAttempts(attempts + 1);
      setTimeout(pollPaymentStatus, pollInterval);
    } catch (error) {
      console.log('Error checking payment status:', error);
      setAttempts(attempts + 1);
      setTimeout(pollPaymentStatus, pollInterval);
    }
  };

  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.content}>
        {status === 'loading' && (
          <>
            <ActivityIndicator size="large" color={colors.primary} />
            <Text style={styles.title}>Processing Payment...</Text>
            <Text style={styles.subtitle}>Please wait while we confirm your subscription</Text>
          </>
        )}

        {status === 'success' && (
          <>
            <View style={styles.successIcon}>
              <Ionicons name="checkmark-circle" size={80} color={colors.success} />
            </View>
            <Text style={styles.title}>Welcome to Premium!</Text>
            <Text style={styles.subtitle}>
              Your subscription is now active. Enjoy unlimited access to all features.
            </Text>
          </>
        )}

        {status === 'error' && (
          <>
            <View style={styles.errorIcon}>
              <Ionicons name="close-circle" size={80} color={colors.error} />
            </View>
            <Text style={styles.title}>Payment Issue</Text>
            <Text style={styles.subtitle}>
              There was an issue processing your payment. Please try again or contact support.
            </Text>
          </>
        )}
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  content: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: 40,
  },
  successIcon: {
    marginBottom: 24,
  },
  errorIcon: {
    marginBottom: 24,
  },
  title: {
    fontSize: 24,
    fontWeight: '700',
    color: colors.text,
    textAlign: 'center',
    marginTop: 16,
  },
  subtitle: {
    fontSize: 16,
    color: colors.textSecondary,
    textAlign: 'center',
    marginTop: 12,
    lineHeight: 24,
  },
});