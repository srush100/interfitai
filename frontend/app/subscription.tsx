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
  Platform,
  Dimensions,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import { PurchasesPackage } from 'react-native-purchases';
import { useUserStore } from '../src/store/userStore';
import { colors } from '../src/theme/colors';
import useSubscription from '../src/hooks/useSubscription';
import AsyncStorage from '@react-native-async-storage/async-storage';

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

// Fallback plans for web or when RevenueCat offerings aren't available
const FALLBACK_PLANS = [
  {
    id: 'monthly',
    name: 'Monthly',
    price: '$9.99',
    period: '/month',
    isYearly: false,
  },
  {
    id: 'yearly',
    name: 'Annual',
    price: '$59.99',
    period: '/year',
    isYearly: true,
    savings: 'Save 50%',
  },
];

export default function Subscription() {
  const router = useRouter();
  const { profile } = useUserStore();
  
  // RevenueCat subscription hook
  const {
    isLoading,
    isPremium,
    offerings,
    error,
    initialize,
    purchase,
    restore,
    openManagement,
  } = useSubscription();

  const [selectedPackage, setSelectedPackage] = useState<PurchasesPackage | null>(null);
  const [selectedFallbackPlan, setSelectedFallbackPlan] = useState<string>('yearly');
  const [purchasing, setPurchasing] = useState(false);
  const [initAttempted, setInitAttempted] = useState(false);

  // Initialize RevenueCat on mount
  useEffect(() => {
    const initSubscription = async () => {
      try {
        const userId = await AsyncStorage.getItem('@user_id');
        await initialize(userId || undefined);
      } catch (err) {
        console.log('RevenueCat init error:', err);
      } finally {
        setInitAttempted(true);
      }
    };
    initSubscription();
  }, [initialize]);

  // Auto-select first package when offerings load
  useEffect(() => {
    if (offerings?.current?.availablePackages?.length && !selectedPackage) {
      // Prefer annual/yearly package if available
      const packages = offerings.current.availablePackages;
      const yearlyPkg = packages.find(
        p => p.packageType === 'ANNUAL' || 
             p.identifier.includes('annual') || 
             p.identifier.includes('yearly')
      );
      setSelectedPackage(yearlyPkg || packages[0]);
    }
  }, [offerings, selectedPackage]);

  const handlePurchase = async () => {
    if (Platform.OS === 'web') {
      Alert.alert(
        'Mobile Only',
        'Subscriptions are available on iOS and Android. Please download the app to subscribe.',
        [{ text: 'OK' }]
      );
      return;
    }

    if (!selectedPackage) {
      Alert.alert('Error', 'Please select a subscription plan');
      return;
    }
    
    setPurchasing(true);
    const success = await purchase(selectedPackage);
    setPurchasing(false);
    
    if (success) {
      router.back();
    }
  };

  const handleRestore = async () => {
    if (Platform.OS === 'web') {
      Alert.alert(
        'Mobile Only',
        'Please use the mobile app to restore purchases.',
        [{ text: 'OK' }]
      );
      return;
    }

    setPurchasing(true);
    await restore();
    setPurchasing(false);
  };

  // If already premium, show management screen
  if (isPremium) {
    return (
      <SafeAreaView style={styles.container}>
        <View style={styles.header}>
          <TouchableOpacity onPress={() => router.back()} style={styles.backBtn}>
            <Ionicons name="arrow-back" size={24} color={colors.text} />
          </TouchableOpacity>
          <Text style={styles.headerTitle}>Premium</Text>
          <View style={{ width: 40 }} />
        </View>
        
        <View style={styles.premiumActiveContainer}>
          <LinearGradient
            colors={[colors.primary, '#C4A000']}
            start={{ x: 0, y: 0 }}
            end={{ x: 1, y: 1 }}
            style={styles.premiumBadgeGradient}
          >
            <Ionicons name="checkmark-circle" size={50} color="#000" />
          </LinearGradient>
          <Text style={styles.premiumActiveTitle}>You're Premium!</Text>
          <Text style={styles.premiumActiveSubtitle}>
            You have full access to all InterFitAI features
          </Text>
          
          <TouchableOpacity style={styles.manageBtn} onPress={openManagement}>
            <Text style={styles.manageBtnText}>Manage Subscription</Text>
            <Ionicons name="open-outline" size={18} color={colors.primary} />
          </TouchableOpacity>
          
          <TouchableOpacity 
            style={styles.doneBtn} 
            onPress={() => router.back()}
          >
            <Text style={styles.doneBtnText}>Done</Text>
          </TouchableOpacity>
        </View>
      </SafeAreaView>
    );
  }

  // Show loading while initializing (but only briefly)
  if (isLoading && !initAttempted) {
    return (
      <SafeAreaView style={styles.container}>
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color={colors.primary} />
          <Text style={styles.loadingText}>Loading subscription options...</Text>
        </View>
      </SafeAreaView>
    );
  }

  // Get packages from RevenueCat or use fallback
  const packages = offerings?.current?.availablePackages || [];
  const useFallback = packages.length === 0;

  return (
    <SafeAreaView style={styles.container}>
      <ScrollView showsVerticalScrollIndicator={false}>
        {/* Header */}
        <View style={styles.header}>
          <TouchableOpacity onPress={() => router.back()} style={styles.backBtn}>
            <Ionicons name="close" size={24} color={colors.text} />
          </TouchableOpacity>
          <View style={{ flex: 1 }} />
          <TouchableOpacity onPress={handleRestore} disabled={purchasing}>
            <Text style={styles.restoreText}>Restore</Text>
          </TouchableOpacity>
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

        {/* Subscription Options */}
        <View style={styles.packagesSection}>
          <Text style={styles.sectionTitle}>Choose Your Plan</Text>
          
          {/* RevenueCat Packages */}
          {!useFallback && packages.map((pkg) => {
            const isSelected = selectedPackage?.identifier === pkg.identifier;
            const isYearly = pkg.packageType === 'ANNUAL' || 
                            pkg.identifier.includes('annual') || 
                            pkg.identifier.includes('yearly');
            
            return (
              <TouchableOpacity
                key={pkg.identifier}
                style={[styles.packageCard, isSelected && styles.packageCardSelected]}
                onPress={() => setSelectedPackage(pkg)}
              >
                {isYearly && (
                  <View style={styles.saveBadge}>
                    <Text style={styles.saveBadgeText}>BEST VALUE</Text>
                  </View>
                )}
                <View style={styles.packageRadio}>
                  <View style={[styles.radioOuter, isSelected && styles.radioOuterSelected]}>
                    {isSelected && <View style={styles.radioInner} />}
                  </View>
                </View>
                <View style={styles.packageInfo}>
                  <Text style={styles.packageTitle}>
                    {isYearly ? 'Annual' : 'Monthly'}
                  </Text>
                  <Text style={styles.packagePrice}>
                    {pkg.product.priceString}
                    <Text style={styles.packagePeriod}>
                      /{isYearly ? 'year' : 'month'}
                    </Text>
                  </Text>
                  {isYearly && (
                    <Text style={styles.packageSavings}>
                      Save up to 50% vs monthly
                    </Text>
                  )}
                </View>
              </TouchableOpacity>
            );
          })}

          {/* Fallback Plans (for web or when RevenueCat unavailable) */}
          {useFallback && FALLBACK_PLANS.map((plan) => {
            const isSelected = selectedFallbackPlan === plan.id;
            
            return (
              <TouchableOpacity
                key={plan.id}
                style={[styles.packageCard, isSelected && styles.packageCardSelected]}
                onPress={() => setSelectedFallbackPlan(plan.id)}
              >
                {plan.isYearly && (
                  <View style={styles.saveBadge}>
                    <Text style={styles.saveBadgeText}>BEST VALUE</Text>
                  </View>
                )}
                <View style={styles.packageRadio}>
                  <View style={[styles.radioOuter, isSelected && styles.radioOuterSelected]}>
                    {isSelected && <View style={styles.radioInner} />}
                  </View>
                </View>
                <View style={styles.packageInfo}>
                  <Text style={styles.packageTitle}>{plan.name}</Text>
                  <Text style={styles.packagePrice}>
                    {plan.price}
                    <Text style={styles.packagePeriod}>{plan.period}</Text>
                  </Text>
                  {plan.savings && (
                    <Text style={styles.packageSavings}>{plan.savings}</Text>
                  )}
                </View>
              </TouchableOpacity>
            );
          })}
        </View>

        {/* Error Message */}
        {error && (
          <View style={styles.errorContainer}>
            <Text style={styles.errorText}>{error}</Text>
          </View>
        )}

        {/* Web Notice */}
        {Platform.OS === 'web' && (
          <View style={styles.webNotice}>
            <Ionicons name="information-circle" size={20} color={colors.primary} />
            <Text style={styles.webNoticeText}>
              Subscriptions are processed through the App Store or Google Play. 
              Download the mobile app to subscribe.
            </Text>
          </View>
        )}

        {/* Terms */}
        <View style={styles.termsSection}>
          <Text style={styles.termsText}>
            Payment will be charged to your {Platform.OS === 'ios' ? 'Apple ID' : Platform.OS === 'android' ? 'Google Play' : 'app store'} account.
            Subscription auto-renews unless canceled at least 24 hours before the end of the current period.
          </Text>
          <View style={styles.termsLinks}>
            <TouchableOpacity>
              <Text style={styles.termsLink}>Terms of Service</Text>
            </TouchableOpacity>
            <Text style={styles.termsDot}>•</Text>
            <TouchableOpacity>
              <Text style={styles.termsLink}>Privacy Policy</Text>
            </TouchableOpacity>
          </View>
        </View>
      </ScrollView>

      {/* Purchase Button */}
      <View style={styles.purchaseContainer}>
        <TouchableOpacity
          style={[styles.purchaseBtn, purchasing && styles.purchaseBtnDisabled]}
          onPress={handlePurchase}
          disabled={purchasing}
        >
          {purchasing ? (
            <ActivityIndicator color="#000" />
          ) : (
            <Text style={styles.purchaseBtnText}>
              {Platform.OS === 'web' ? 'Download App to Subscribe' : 'Subscribe Now'}
            </Text>
          )}
        </TouchableOpacity>
      </View>
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
    gap: 16,
  },
  loadingText: {
    color: colors.textSecondary,
    fontSize: 16,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingVertical: 12,
  },
  headerTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: colors.text,
  },
  backBtn: {
    width: 40,
    height: 40,
    justifyContent: 'center',
    alignItems: 'center',
  },
  restoreText: {
    color: colors.primary,
    fontSize: 15,
    fontWeight: '600',
  },
  heroSection: {
    alignItems: 'center',
    paddingVertical: 24,
    paddingHorizontal: 20,
  },
  heroGradient: {
    width: 100,
    height: 100,
    borderRadius: 50,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 16,
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
    paddingHorizontal: 20,
    paddingBottom: 24,
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
    marginBottom: 2,
  },
  featureDescription: {
    fontSize: 13,
    color: colors.textSecondary,
  },
  packagesSection: {
    paddingHorizontal: 20,
    paddingBottom: 20,
  },
  sectionTitle: {
    fontSize: 18,
    fontWeight: '700',
    color: colors.text,
    marginBottom: 16,
  },
  packageCard: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.surface,
    borderRadius: 16,
    padding: 16,
    marginBottom: 12,
    borderWidth: 2,
    borderColor: colors.border,
    position: 'relative',
    overflow: 'hidden',
  },
  packageCardSelected: {
    borderColor: colors.primary,
    backgroundColor: colors.primary + '10',
  },
  saveBadge: {
    position: 'absolute',
    top: 0,
    right: 0,
    backgroundColor: colors.primary,
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderBottomLeftRadius: 8,
  },
  saveBadgeText: {
    fontSize: 10,
    fontWeight: '700',
    color: '#000',
  },
  packageRadio: {
    marginRight: 12,
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
  packageInfo: {
    flex: 1,
  },
  packageTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: colors.text,
    marginBottom: 4,
  },
  packagePrice: {
    fontSize: 22,
    fontWeight: '700',
    color: colors.text,
  },
  packagePeriod: {
    fontSize: 14,
    fontWeight: '400',
    color: colors.textSecondary,
  },
  packageSavings: {
    fontSize: 12,
    color: colors.primary,
    fontWeight: '600',
    marginTop: 4,
  },
  errorContainer: {
    marginHorizontal: 20,
    padding: 12,
    backgroundColor: '#FF375520',
    borderRadius: 8,
    marginBottom: 16,
  },
  errorText: {
    color: '#FF3755',
    fontSize: 14,
    textAlign: 'center',
  },
  webNotice: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    marginHorizontal: 20,
    padding: 12,
    backgroundColor: colors.primary + '15',
    borderRadius: 8,
    marginBottom: 16,
    gap: 10,
  },
  webNoticeText: {
    flex: 1,
    fontSize: 13,
    color: colors.textSecondary,
    lineHeight: 18,
  },
  termsSection: {
    paddingHorizontal: 20,
    paddingBottom: 120,
  },
  termsText: {
    fontSize: 12,
    color: colors.textMuted,
    textAlign: 'center',
    lineHeight: 18,
    marginBottom: 8,
  },
  termsLinks: {
    flexDirection: 'row',
    justifyContent: 'center',
    alignItems: 'center',
  },
  termsLink: {
    fontSize: 12,
    color: colors.primary,
  },
  termsDot: {
    color: colors.textMuted,
    marginHorizontal: 8,
  },
  purchaseContainer: {
    position: 'absolute',
    bottom: 0,
    left: 0,
    right: 0,
    padding: 20,
    paddingBottom: Platform.OS === 'ios' ? 34 : 20,
    backgroundColor: colors.background,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  purchaseBtn: {
    backgroundColor: colors.primary,
    paddingVertical: 16,
    borderRadius: 12,
    alignItems: 'center',
  },
  purchaseBtnDisabled: {
    opacity: 0.6,
  },
  purchaseBtnText: {
    fontSize: 18,
    fontWeight: '700',
    color: '#000',
  },
  premiumActiveContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: 40,
  },
  premiumBadgeGradient: {
    width: 100,
    height: 100,
    borderRadius: 50,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 24,
  },
  premiumActiveTitle: {
    fontSize: 26,
    fontWeight: '700',
    color: colors.text,
    marginBottom: 8,
  },
  premiumActiveSubtitle: {
    fontSize: 16,
    color: colors.textSecondary,
    textAlign: 'center',
    marginBottom: 32,
  },
  manageBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    paddingVertical: 12,
    paddingHorizontal: 24,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: colors.primary,
    marginBottom: 16,
  },
  manageBtnText: {
    fontSize: 16,
    fontWeight: '600',
    color: colors.primary,
  },
  doneBtn: {
    paddingVertical: 12,
    paddingHorizontal: 40,
  },
  doneBtnText: {
    fontSize: 16,
    color: colors.textSecondary,
  },
});
