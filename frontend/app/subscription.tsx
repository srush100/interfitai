import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  ActivityIndicator,
  Linking,
  Alert,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import Constants from 'expo-constants';
import { useUserStore } from '../src/store/userStore';
import { colors } from '../src/theme/colors';
import api from '../src/services/api';

interface Plan {
  id: string;
  name: string;
  price: number;
  duration: string;
  perMonth: number;
  savings?: string;
  features: string[];
  popular?: boolean;
}

const PLANS: Plan[] = [
  {
    id: 'monthly',
    name: 'Monthly',
    price: 9.99,
    duration: '1 month',
    perMonth: 9.99,
    features: [
      'AI Workout Programs',
      'AI Meal Plans',
      'Food Tracking & Analysis',
      'Ask InterFitAI',
      'Step Tracking',
    ],
  },
  {
    id: 'quarterly',
    name: 'Quarterly',
    price: 24.99,
    duration: '3 months',
    perMonth: 8.33,
    savings: 'Save 17%',
    popular: true,
    features: [
      'AI Workout Programs',
      'AI Meal Plans',
      'Food Tracking & Analysis',
      'Ask InterFitAI',
      'Step Tracking',
      'Priority Support',
    ],
  },
  {
    id: 'yearly',
    name: 'Yearly',
    price: 79.99,
    duration: '12 months',
    perMonth: 6.67,
    savings: 'Save 33%',
    features: [
      'AI Workout Programs',
      'AI Meal Plans',
      'Food Tracking & Analysis',
      'Ask InterFitAI',
      'Step Tracking',
      'Priority Support',
      'Exclusive Content',
    ],
  },
];

export default function Subscription() {
  const router = useRouter();
  const { profile, loadProfile } = useUserStore();
  const [selectedPlan, setSelectedPlan] = useState('quarterly');
  const [loading, setLoading] = useState(false);

  const handleSubscribe = async () => {
    if (!profile?.id) {
      Alert.alert('Error', 'Please set up your profile first');
      return;
    }

    setLoading(true);
    try {
      const backendUrl = Constants.expoConfig?.extra?.EXPO_PUBLIC_BACKEND_URL ||
                         process.env.EXPO_PUBLIC_BACKEND_URL ||
                         'https://ai-fitness-pro-4.preview.emergentagent.com';

      const response = await api.post('/subscription/checkout', {
        user_id: profile.id,
        plan_id: selectedPlan,
        origin_url: backendUrl,
      });

      if (response.data.url) {
        // Open Stripe checkout
        await Linking.openURL(response.data.url);
      }
    } catch (error: any) {
      Alert.alert('Error', error.response?.data?.detail || 'Failed to start checkout');
    } finally {
      setLoading(false);
    }
  };

  const isSubscribed = profile?.subscription_status && profile.subscription_status !== 'free';

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backBtn}>
          <Ionicons name="arrow-back" size={24} color={colors.text} />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Premium</Text>
        <View style={styles.backBtn} />
      </View>

      <ScrollView contentContainerStyle={styles.scrollContent} showsVerticalScrollIndicator={false}>
        {/* Hero */}
        <View style={styles.hero}>
          <View style={styles.heroIcon}>
            <Ionicons name="diamond" size={48} color={colors.primary} />
          </View>
          <Text style={styles.heroTitle}>Unlock Your Full Potential</Text>
          <Text style={styles.heroSubtitle}>
            Get unlimited access to AI-powered workouts, meal plans, and personalized coaching
          </Text>
        </View>

        {isSubscribed && (
          <View style={styles.activeCard}>
            <Ionicons name="checkmark-circle" size={24} color={colors.success} />
            <View style={styles.activeInfo}>
              <Text style={styles.activeTitle}>You're Subscribed!</Text>
              <Text style={styles.activeText}>
                {profile.subscription_status} plan active
              </Text>
            </View>
          </View>
        )}

        {/* Plans */}
        <Text style={styles.sectionTitle}>Choose Your Plan</Text>
        {PLANS.map((plan) => (
          <TouchableOpacity
            key={plan.id}
            style={[
              styles.planCard,
              selectedPlan === plan.id && styles.planCardActive,
              plan.popular && styles.planCardPopular,
            ]}
            onPress={() => setSelectedPlan(plan.id)}
          >
            {plan.popular && (
              <View style={styles.popularBadge}>
                <Text style={styles.popularText}>Most Popular</Text>
              </View>
            )}

            <View style={styles.planHeader}>
              <View style={styles.planInfo}>
                <Text style={[styles.planName, selectedPlan === plan.id && styles.planNameActive]}>
                  {plan.name}
                </Text>
                <Text style={styles.planDuration}>{plan.duration}</Text>
              </View>
              <View style={styles.planPricing}>
                <Text style={[styles.planPrice, selectedPlan === plan.id && styles.planPriceActive]}>
                  ${plan.price}
                </Text>
                {plan.savings && (
                  <View style={styles.savingsBadge}>
                    <Text style={styles.savingsText}>{plan.savings}</Text>
                  </View>
                )}
              </View>
            </View>

            <Text style={styles.perMonth}>
              ${plan.perMonth.toFixed(2)}/month
            </Text>

            {selectedPlan === plan.id && (
              <View style={styles.planFeatures}>
                {plan.features.map((feature, idx) => (
                  <View key={idx} style={styles.featureRow}>
                    <Ionicons name="checkmark-circle" size={18} color={colors.success} />
                    <Text style={styles.featureText}>{feature}</Text>
                  </View>
                ))}
              </View>
            )}
          </TouchableOpacity>
        ))}

        {/* Subscribe Button */}
        {!isSubscribed && (
          <TouchableOpacity
            style={[styles.subscribeBtn, loading && styles.subscribeBtnDisabled]}
            onPress={handleSubscribe}
            disabled={loading}
          >
            {loading ? (
              <ActivityIndicator size="small" color={colors.background} />
            ) : (
              <>
                <Text style={styles.subscribeBtnText}>Subscribe Now</Text>
                <Ionicons name="arrow-forward" size={20} color={colors.background} />
              </>
            )}
          </TouchableOpacity>
        )}

        {/* Footer */}
        <View style={styles.footer}>
          <Text style={styles.footerText}>
            Cancel anytime. Payments are processed securely via Stripe.
          </Text>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: 16,
  },
  backBtn: {
    width: 40,
    height: 40,
    justifyContent: 'center',
    alignItems: 'center',
  },
  headerTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: colors.text,
  },
  scrollContent: {
    padding: 20,
    paddingBottom: 40,
  },
  hero: {
    alignItems: 'center',
    marginBottom: 32,
  },
  heroIcon: {
    width: 80,
    height: 80,
    borderRadius: 40,
    backgroundColor: colors.primary + '20',
    justifyContent: 'center',
    alignItems: 'center',
  },
  heroTitle: {
    fontSize: 24,
    fontWeight: '700',
    color: colors.text,
    marginTop: 16,
    textAlign: 'center',
  },
  heroSubtitle: {
    fontSize: 15,
    color: colors.textSecondary,
    textAlign: 'center',
    marginTop: 8,
    paddingHorizontal: 20,
  },
  activeCard: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.success + '20',
    padding: 16,
    borderRadius: 12,
    marginBottom: 24,
    gap: 12,
  },
  activeInfo: {
    flex: 1,
  },
  activeTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: colors.text,
  },
  activeText: {
    fontSize: 14,
    color: colors.textSecondary,
    marginTop: 2,
    textTransform: 'capitalize',
  },
  sectionTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: colors.text,
    marginBottom: 16,
  },
  planCard: {
    backgroundColor: colors.surface,
    borderRadius: 16,
    padding: 20,
    marginBottom: 12,
    borderWidth: 2,
    borderColor: colors.border,
  },
  planCardActive: {
    borderColor: colors.primary,
    backgroundColor: colors.primary + '08',
  },
  planCardPopular: {
    borderColor: colors.primary,
  },
  popularBadge: {
    position: 'absolute',
    top: -10,
    right: 16,
    backgroundColor: colors.primary,
    paddingHorizontal: 12,
    paddingVertical: 4,
    borderRadius: 12,
  },
  popularText: {
    fontSize: 11,
    fontWeight: '700',
    color: colors.background,
  },
  planHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
  },
  planInfo: {
    flex: 1,
  },
  planName: {
    fontSize: 20,
    fontWeight: '700',
    color: colors.text,
  },
  planNameActive: {
    color: colors.primary,
  },
  planDuration: {
    fontSize: 14,
    color: colors.textSecondary,
    marginTop: 2,
  },
  planPricing: {
    alignItems: 'flex-end',
  },
  planPrice: {
    fontSize: 28,
    fontWeight: '700',
    color: colors.text,
  },
  planPriceActive: {
    color: colors.primary,
  },
  savingsBadge: {
    backgroundColor: colors.success + '20',
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 8,
    marginTop: 4,
  },
  savingsText: {
    fontSize: 11,
    fontWeight: '600',
    color: colors.success,
  },
  perMonth: {
    fontSize: 14,
    color: colors.textSecondary,
    marginTop: 8,
  },
  planFeatures: {
    marginTop: 16,
    paddingTop: 16,
    borderTopWidth: 1,
    borderTopColor: colors.border,
    gap: 10,
  },
  featureRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
  },
  featureText: {
    fontSize: 14,
    color: colors.text,
  },
  subscribeBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.primary,
    padding: 18,
    borderRadius: 28,
    marginTop: 24,
    gap: 8,
  },
  subscribeBtnDisabled: {
    opacity: 0.7,
  },
  subscribeBtnText: {
    fontSize: 18,
    fontWeight: '700',
    color: colors.background,
  },
  footer: {
    marginTop: 24,
    alignItems: 'center',
  },
  footerText: {
    fontSize: 12,
    color: colors.textMuted,
    textAlign: 'center',
  },
});