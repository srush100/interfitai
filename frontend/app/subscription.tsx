import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  ActivityIndicator,
  Platform,
  Dimensions,
  Image,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import { useUserStore } from '../src/store/userStore';
import { colors } from '../src/theme/colors';
import AsyncStorage from '@react-native-async-storage/async-storage';
import api from '../src/services/api';

const { width } = Dimensions.get('window');

// Premium features list
const PREMIUM_FEATURES = [
  {
    icon: 'nutrition',
    title: 'AI Meal Plans',
    description: 'Personalized meal plans with exact macros',
  },
  {
    icon: 'barbell',
    title: 'Custom Workouts',
    description: 'AI-generated workout programs',
  },
  {
    icon: 'body',
    title: 'Body Analysis',
    description: 'Track progress with AI body composition',
  },
  {
    icon: 'chatbubbles',
    title: 'Ask InterFitAI',
    description: 'Unlimited AI fitness coaching',
  },
  {
    icon: 'analytics',
    title: 'Advanced Analytics',
    description: 'Detailed insights and progress tracking',
  },
  {
    icon: 'cloud-download',
    title: 'Offline Access',
    description: 'Download plans for offline use',
  },
];

// Subscription plans
const PLANS = [
  {
    id: 'monthly',
    name: 'Monthly',
    price: 9.99,
    priceDisplay: '$9.99',
    period: '/month',
    dailyCost: '$0.33/day',
    popular: false,
  },
  {
    id: 'quarterly',
    name: 'Quarterly',
    price: 29.99,
    priceDisplay: '$29.99',
    period: '/3 months',
    dailyCost: '$0.33/day',
    savings: 'Save $0',
    popular: false,
  },
  {
    id: 'yearly',
    name: 'Annual',
    price: 79.99,
    priceDisplay: '$79.99',
    period: '/year',
    dailyCost: '$0.22/day',
    savings: 'Save 33%',
    popular: true,
  },
];

export default function Subscription() {
  const router = useRouter();
  const { profile } = useUserStore();
  
  const [isPremium, setIsPremium] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [selectedPlan, setSelectedPlan] = useState('yearly');

  // Check premium status on mount
  useEffect(() => {
    checkPremiumStatus();
  }, []);

  const checkPremiumStatus = async () => {
    try {
      setIsLoading(true);
      const userId = await AsyncStorage.getItem('@user_id');
      if (userId) {
        const response = await api.get(`/subscription/check/${userId}`);
        if (response.data?.has_access) {
          setIsPremium(true);
        }
      }
    } catch (err) {
      console.log('Premium check error:', err);
    } finally {
      setIsLoading(false);
    }
  };

  const handleClose = () => {
    router.back();
  };

  // Show loading
  if (isLoading) {
    return (
      <SafeAreaView style={styles.container}>
        <View style={styles.loadingContainer}>
          <View style={styles.logoGlow}>
            <Image
              source={require('../assets/logo-icon-yellow.png')}
              style={styles.loadingLogo}
              resizeMode="contain"
            />
          </View>
          <ActivityIndicator size="large" color={colors.primary} style={{ marginTop: 20 }} />
          <Text style={styles.loadingText}>Loading...</Text>
        </View>
      </SafeAreaView>
    );
  }

  // If already premium, show success screen
  if (isPremium) {
    return (
      <SafeAreaView style={styles.container}>
        <View style={styles.header}>
          <TouchableOpacity onPress={handleClose} style={styles.closeBtn}>
            <Ionicons name="close" size={24} color={colors.text} />
          </TouchableOpacity>
          <Text style={styles.headerTitle}>Premium</Text>
          <View style={{ width: 40 }} />
        </View>
        
        <View style={styles.premiumActiveContainer}>
          <LinearGradient
            colors={[colors.primary, '#C4A000']}
            start={{ x: 0, y: 0 }}
            end={{ x: 1, y: 1 }}
            style={styles.premiumBadge}
          >
            <Ionicons name="checkmark-circle" size={60} color="#000" />
          </LinearGradient>
          <Text style={styles.premiumTitle}>You're Premium!</Text>
          <Text style={styles.premiumSubtitle}>
            You have full access to all InterFitAI features
          </Text>
          
          <TouchableOpacity style={styles.doneBtn} onPress={handleClose}>
            <Text style={styles.doneBtnText}>Done</Text>
          </TouchableOpacity>
        </View>
      </SafeAreaView>
    );
  }

  // Show subscription options
  return (
    <SafeAreaView style={styles.container}>
      <ScrollView showsVerticalScrollIndicator={false}>
        {/* Header */}
        <View style={styles.header}>
          <TouchableOpacity onPress={handleClose} style={styles.closeBtn}>
            <Ionicons name="close" size={24} color={colors.text} />
          </TouchableOpacity>
          <View style={{ flex: 1 }} />
          <View style={{ width: 40 }} />
        </View>

        {/* Hero Section */}
        <View style={styles.heroSection}>
          <LinearGradient
            colors={[colors.primary, '#C4A000']}
            start={{ x: 0, y: 0 }}
            end={{ x: 1, y: 1 }}
            style={styles.heroGradient}
          >
            <Ionicons name="diamond" size={50} color="#000" />
          </LinearGradient>
          <Text style={styles.heroTitle}>Unlock Premium</Text>
          <Text style={styles.heroSubtitle}>
            Get unlimited access to all InterFitAI features
          </Text>
        </View>

        {/* Features List */}
        <View style={styles.featuresSection}>
          {PREMIUM_FEATURES.map((feature, index) => (
            <View key={index} style={styles.featureItem}>
              <View style={styles.featureIcon}>
                <Ionicons name={feature.icon as any} size={22} color={colors.primary} />
              </View>
              <View style={styles.featureText}>
                <Text style={styles.featureTitle}>{feature.title}</Text>
                <Text style={styles.featureDescription}>{feature.description}</Text>
              </View>
              <Ionicons name="checkmark-circle" size={22} color={colors.primary} />
            </View>
          ))}
        </View>

        {/* Plan Selection */}
        <View style={styles.plansSection}>
          <Text style={styles.plansSectionTitle}>Choose Your Plan</Text>
          
          {PLANS.map((plan) => (
            <TouchableOpacity
              key={plan.id}
              style={[
                styles.planCard,
                selectedPlan === plan.id && styles.planCardSelected,
                plan.popular && styles.planCardPopular,
              ]}
              onPress={() => setSelectedPlan(plan.id)}
            >
              {plan.popular && (
                <View style={styles.popularBadge}>
                  <Text style={styles.popularText}>BEST VALUE</Text>
                </View>
              )}
              <View style={styles.planLeft}>
                <View style={[
                  styles.radioOuter,
                  selectedPlan === plan.id && styles.radioOuterSelected
                ]}>
                  {selectedPlan === plan.id && <View style={styles.radioInner} />}
                </View>
                <View>
                  <Text style={styles.planName}>{plan.name}</Text>
                  {plan.savings && (
                    <Text style={styles.planSavings}>{plan.savings}</Text>
                  )}
                </View>
              </View>
              <View style={styles.planRight}>
                <Text style={styles.planPrice}>{plan.priceDisplay}</Text>
                <Text style={styles.planPeriod}>{plan.period}</Text>
                <Text style={styles.planDaily}>{plan.dailyCost}</Text>
              </View>
            </TouchableOpacity>
          ))}
        </View>

        {/* Subscribe Button */}
        <View style={styles.subscribeSection}>
          <TouchableOpacity style={styles.subscribeBtn}>
            <LinearGradient
              colors={[colors.primary, '#D4AF37']}
              start={{ x: 0, y: 0 }}
              end={{ x: 1, y: 0 }}
              style={styles.subscribeBtnGradient}
            >
              <Text style={styles.subscribeBtnText}>
                {Platform.OS === 'web' ? 'Download App to Subscribe' : 'Start Free Trial'}
              </Text>
            </LinearGradient>
          </TouchableOpacity>
          
          <Text style={styles.trialText}>
            3-day free trial, then {PLANS.find(p => p.id === selectedPlan)?.priceDisplay}{PLANS.find(p => p.id === selectedPlan)?.period}
          </Text>
          <Text style={styles.cancelText}>Cancel anytime. No commitment.</Text>
        </View>

        {/* Terms */}
        <View style={styles.termsSection}>
          <Text style={styles.termsText}>
            By subscribing, you agree to our Terms of Service and Privacy Policy.
            Subscription auto-renews unless canceled at least 24 hours before the end of the current period.
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
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  logoGlow: {
    width: 100,
    height: 100,
    borderRadius: 50,
    backgroundColor: 'rgba(255, 204, 0, 0.15)',
    borderWidth: 2,
    borderColor: 'rgba(255, 204, 0, 0.3)',
    justifyContent: 'center',
    alignItems: 'center',
  },
  loadingLogo: {
    width: 60,
    height: 60,
  },
  loadingText: {
    marginTop: 16,
    fontSize: 16,
    color: colors.textSecondary,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingVertical: 12,
  },
  closeBtn: {
    padding: 8,
  },
  headerTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: colors.text,
  },
  heroSection: {
    alignItems: 'center',
    paddingVertical: 24,
    paddingHorizontal: 24,
  },
  heroGradient: {
    width: 100,
    height: 100,
    borderRadius: 50,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 20,
  },
  heroTitle: {
    fontSize: 28,
    fontWeight: '700',
    color: colors.text,
    marginBottom: 8,
  },
  heroSubtitle: {
    fontSize: 16,
    color: colors.textSecondary,
    textAlign: 'center',
  },
  featuresSection: {
    paddingHorizontal: 24,
    marginBottom: 24,
  },
  featureItem: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  featureIcon: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: colors.primary + '20',
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 12,
  },
  featureText: {
    flex: 1,
  },
  featureTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: colors.text,
  },
  featureDescription: {
    fontSize: 13,
    color: colors.textSecondary,
    marginTop: 2,
  },
  plansSection: {
    paddingHorizontal: 24,
    marginBottom: 24,
  },
  plansSectionTitle: {
    fontSize: 20,
    fontWeight: '700',
    color: colors.text,
    marginBottom: 16,
  },
  planCard: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    backgroundColor: colors.surface,
    borderRadius: 16,
    padding: 16,
    marginBottom: 12,
    borderWidth: 2,
    borderColor: colors.border,
  },
  planCardSelected: {
    borderColor: colors.primary,
    backgroundColor: colors.primary + '10',
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
    fontSize: 10,
    fontWeight: '700',
    color: '#000',
  },
  planLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  radioOuter: {
    width: 24,
    height: 24,
    borderRadius: 12,
    borderWidth: 2,
    borderColor: colors.border,
    justifyContent: 'center',
    alignItems: 'center',
  },
  radioOuterSelected: {
    borderColor: colors.primary,
  },
  radioInner: {
    width: 12,
    height: 12,
    borderRadius: 6,
    backgroundColor: colors.primary,
  },
  planName: {
    fontSize: 16,
    fontWeight: '600',
    color: colors.text,
  },
  planSavings: {
    fontSize: 12,
    color: colors.success,
    fontWeight: '600',
    marginTop: 2,
  },
  planRight: {
    alignItems: 'flex-end',
  },
  planPrice: {
    fontSize: 20,
    fontWeight: '700',
    color: colors.text,
  },
  planPeriod: {
    fontSize: 12,
    color: colors.textSecondary,
  },
  planDaily: {
    fontSize: 11,
    color: colors.primary,
    marginTop: 4,
  },
  subscribeSection: {
    paddingHorizontal: 24,
    marginBottom: 16,
  },
  subscribeBtn: {
    borderRadius: 16,
    overflow: 'hidden',
  },
  subscribeBtnGradient: {
    paddingVertical: 18,
    alignItems: 'center',
  },
  subscribeBtnText: {
    fontSize: 18,
    fontWeight: '700',
    color: '#000',
  },
  trialText: {
    fontSize: 14,
    color: colors.textSecondary,
    textAlign: 'center',
    marginTop: 12,
  },
  cancelText: {
    fontSize: 12,
    color: colors.textMuted,
    textAlign: 'center',
    marginTop: 4,
  },
  termsSection: {
    paddingHorizontal: 24,
    paddingBottom: 40,
  },
  termsText: {
    fontSize: 11,
    color: colors.textMuted,
    textAlign: 'center',
    lineHeight: 16,
  },
  premiumActiveContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: 24,
  },
  premiumBadge: {
    width: 120,
    height: 120,
    borderRadius: 60,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 24,
  },
  premiumTitle: {
    fontSize: 28,
    fontWeight: '700',
    color: colors.text,
    marginBottom: 8,
  },
  premiumSubtitle: {
    fontSize: 16,
    color: colors.textSecondary,
    textAlign: 'center',
    marginBottom: 32,
  },
  doneBtn: {
    backgroundColor: colors.primary,
    paddingVertical: 16,
    paddingHorizontal: 48,
    borderRadius: 12,
  },
  doneBtnText: {
    fontSize: 18,
    fontWeight: '600',
    color: '#000',
  },
});
