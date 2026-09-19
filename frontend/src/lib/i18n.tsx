import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import type { Language } from './types'

/**
 * Every string appears in both languages. Nepali is not an afterthought
 * bolted onto an English app: a missing Nepali string falls back to English
 * loudly enough to notice in review, rather than silently rendering blank.
 */
const STRINGS = {
  'app.name': ['Sahayatri', 'सहयात्री'],
  'app.tagline': ['Report. Track. Resolve.', 'उजुरी गर्नुहोस्। ट्र्याक गर्नुहोस्। समाधान।'],

  'nav.home': ['Home', 'गृहपृष्ठ'],
  'nav.report': ['Report', 'उजुरी'],
  'nav.myReports': ['My Reports', 'मेरा उजुरी'],
  'nav.nearby': ['Nearby', 'नजिकै'],
  'nav.services': ['Services', 'सेवाहरू'],
  'nav.alerts': ['Alerts', 'सूचना'],
  'nav.sos': ['SOS', 'आपतकाल'],
  'nav.dashboard': ['Dashboard', 'ड्यासबोर्ड'],
  'nav.reviewQueue': ['Duplicates', 'नक्कल'],
  'nav.sosQueue': ['Emergencies', 'आपतकाल'],
  'nav.publishAlert': ['Publish Alert', 'सूचना जारी'],
  'nav.approvals': ['Approvals', 'स्वीकृति'],
  'nav.notifications': ['Notifications', 'सूचनाहरू'],
  'nav.logout': ['Sign out', 'साइन आउट'],
  'nav.menu': ['Menu', 'मेनु'],

  'auth.login': ['Sign in', 'साइन इन'],
  'auth.register': ['Create account', 'खाता खोल्नुहोस्'],
  'auth.email': ['Email', 'इमेल'],
  'auth.password': ['Password', 'पासवर्ड'],
  'auth.fullName': ['Full name', 'पूरा नाम'],
  'auth.phone': ['Phone number', 'फोन नम्बर'],
  'auth.noAccount': ['New here?', 'नयाँ हुनुहुन्छ?'],
  'auth.haveAccount': ['Already have an account?', 'पहिले नै खाता छ?'],
  'auth.accountType': ['Account type', 'खाताको प्रकार'],
  'auth.citizen': ['Citizen', 'नागरिक'],
  'auth.authority': ['Ward / municipality officer', 'वडा / नगरपालिका अधिकारी'],
  'auth.municipality': ['Municipality', 'नगरपालिका'],
  'auth.ward': ['Ward', 'वडा'],
  'auth.selectMunicipality': ['Select a municipality', 'नगरपालिका छान्नुहोस्'],
  'auth.selectWard': ['Select a ward', 'वडा छान्नुहोस्'],
  'auth.signingIn': ['Signing in...', 'साइन इन हुँदै...'],
  'auth.creating': ['Creating account...', 'खाता खोल्दै...'],

  'report.title': ['Report an issue', 'समस्या रिपोर्ट गर्नुहोस्'],
  'report.description': ['What is the problem?', 'समस्या के हो?'],
  'report.descriptionHint': [
    'Describe it in Nepali or English. Be specific about the location.',
    'नेपाली वा अंग्रेजीमा वर्णन गर्नुहोस्। स्थान स्पष्ट लेख्नुहोस्।',
  ],
  'report.category': ['Category', 'श्रेणी'],
  'report.categoryAuto': ['Detect automatically', 'स्वतः पत्ता लगाउनुहोस्'],
  'report.location': ['Location', 'स्थान'],
  'report.useMyLocation': ['Use my location', 'मेरो स्थान प्रयोग गर्नुहोस्'],
  'report.locating': ['Finding you...', 'स्थान खोज्दै...'],
  'report.locationNeeded': [
    'Location is required so the right ward receives your report.',
    'सही वडामा उजुरी पुर्‍याउन स्थान आवश्यक छ।',
  ],
  'report.address': ['Nearby landmark (optional)', 'नजिकको चिनारी (वैकल्पिक)'],
  'report.photos': ['Photos', 'तस्बिरहरू'],
  'report.addPhoto': ['Add photo', 'तस्बिर थप्नुहोस्'],
  'report.photoHint': ['Up to 4 photos, 8MB each.', 'बढीमा ४ तस्बिर, प्रत्येक ८MB।'],
  'report.goesToWard': ['Goes to', 'यसमा जान्छ'],
  'report.wardExplainer': [
    'The ward is set by where the problem is, not by where you live.',
    'वडा तपाईं बस्ने ठाउँले होइन, समस्या भएको ठाउँले तय हुन्छ।',
  ],
  'report.submit': ['Submit report', 'उजुरी पेश गर्नुहोस्'],
  'report.submitting': ['Submitting...', 'पेश गर्दै...'],
  'report.submitted': ['Report submitted', 'उजुरी पेश भयो'],
  'report.possibleDuplicates': [
    'This may already be reported',
    'यो पहिले नै रिपोर्ट भइसकेको हुन सक्छ',
  ],
  'report.duplicateNote': [
    'A ward officer will check whether these are the same problem. Your report is recorded either way.',
    'वडा अधिकारीले यी एउटै समस्या हुन् कि जाँच्नुहुनेछ। जे भए पनि तपाईंको उजुरी दर्ता भयो।',
  ],

  'ticket.status': ['Status', 'अवस्था'],
  'ticket.reported': ['Reported', 'रिपोर्ट भयो'],
  'ticket.verified': ['Verified', 'प्रमाणित'],
  'ticket.in_progress': ['In progress', 'काम भइरहेको'],
  'ticket.resolved': ['Resolved', 'समाधान भयो'],
  'ticket.rejected': ['Rejected', 'अस्वीकृत'],
  'ticket.merged': ['Duplicate', 'नक्कल'],
  'ticket.priority': ['Priority', 'प्राथमिकता'],
  'ticket.low': ['Low', 'न्यून'],
  'ticket.medium': ['Medium', 'मध्यम'],
  'ticket.high': ['High', 'उच्च'],
  'ticket.critical': ['Critical', 'अति जरुरी'],

  'priority.title': ['Priority', 'प्राथमिकता'],
  'priority.autoHint': [
    'Set automatically from category severity, how many people reported it, and how long it has gone unresolved.',
    'श्रेणीको गम्भीरता, कति जनाले उजुरी गरे र कति समयदेखि समाधान भएको छैन भन्ने आधारमा स्वतः तय हुन्छ।',
  ],
  'priority.lockedHint': [
    'Set by hand. Automatic scoring and time escalation will not change it until it is cleared.',
    'हातले तोकिएको। नहटाएसम्म स्वतः गणना र समय वृद्धिले यसलाई परिवर्तन गर्दैन।',
  ],
  'priority.manual': ['Set by hand', 'हातले तोकिएको'],
  'priority.setBy': ['Set by', 'तोक्ने'],
  'priority.reason': ['Reason (optional)', 'कारण (वैकल्पिक)'],
  'priority.reasonHint': [
    'Why this is more or less urgent than the system thinks',
    'प्रणालीले सोचेभन्दा किन बढी वा कम जरुरी हो',
  ],
  'priority.clear': ['Return to automatic', 'स्वतः प्रणालीमा फर्काउनुहोस्'],
  'priority.escalated': ['Escalated for age', 'लामो समय भएकाले बढाइएको'],

  'transparency.title': ['Public transparency', 'सार्वजनिक पारदर्शिता'],
  'transparency.hint': [
    'Aggregate numbers only, no login required.',
    'लगइन नचाहिने, समग्र तथ्याङ्क मात्र।',
  ],
  'transparency.total': ['Total reports', 'कुल उजुरी'],
  'transparency.open': ['Open', 'खुला'],
  'transparency.resolved': ['Resolved', 'समाधान भएको'],
  'transparency.resolvedThisMonth': ['Resolved this month', 'यो महिना समाधान भएको'],
  'transparency.medianOverall': [
    'Median time to resolve',
    'समाधान गर्न लाग्ने औसत समय',
  ],
  'transparency.median': ['median', 'औसत'],
  'transparency.medianHint': [
    'The middle value across every resolved report, so one very slow or very fast case does not skew the picture.',
    'सबै समाधान भएका उजुरीहरूको बीचको मान, ताकि एउटा असाधारण ढिलो वा छिटो केसले चित्र बिगार्दैन।',
  ],
  'transparency.byWard': ['By ward', 'वडा अनुसार'],
  'transparency.byCategory': ['By category', 'श्रेणी अनुसार'],
  'transparency.generatedAt': ['Updated', 'अद्यावधिक'],
  'transparency.backToLogin': ['Back to login', 'लगइनमा फर्कनुहोस्'],
  'ticket.reporters': ['reporters', 'रिपोर्टकर्ता'],
  'ticket.alsoReportedBy': ['Also reported by', 'अन्य रिपोर्टकर्ता'],
  'ticket.communityVerified': ['Community verified', 'समुदायद्वारा प्रमाणित'],
  'ticket.confirmations': ['confirmations', 'पुष्टि'],
  'ticket.history': ['History', 'इतिहास'],

  'comments.title': ['Discussion', 'छलफल'],
  'comments.none': [
    'No comments yet. Ask when this will be fixed.',
    'अहिलेसम्म कुनै टिप्पणी छैन। यो कहिले समाधान हुन्छ सोध्नुहोस्।',
  ],
  'comments.someone': ['Someone', 'कसैले'],
  'comments.addLabel': ['Add a comment', 'टिप्पणी थप्नुहोस्'],
  'comments.placeholder': [
    'When will this be fixed?',
    'यो कहिले समाधान हुन्छ?',
  ],
  'comments.post': ['Post', 'पठाउनुहोस्'],
  'comments.role.authority': ['Ward office', 'वडा कार्यालय'],
  'comments.role.admin': ['Admin', 'प्रशासक'],
  'ticket.photos': ['Photos', 'तस्बिरहरू'],
  'ticket.resolution': ['Resolution', 'समाधान'],
  'ticket.reportedBy': ['Reported by', 'रिपोर्ट गर्ने'],
  'ticket.none': ['No reports yet.', 'अहिलेसम्म कुनै उजुरी छैन।'],
  'ticket.noneHint': [
    'Reports you submit will appear here.',
    'तपाईंले पेश गरेका उजुरी यहाँ देखिनेछन्।',
  ],

  'corroborate.title': ['Is this problem real?', 'के यो समस्या साँचो हो?'],
  'corroborate.hint': [
    'You must be near the location to confirm.',
    'पुष्टि गर्न तपाईं स्थान नजिक हुनुपर्छ।',
  ],
  'corroborate.yes': ['Yes, I can see it', 'हो, मैले देखेको छु'],
  'corroborate.no': ['No, this is not there', 'होइन, यो छैन'],
  'corroborate.done': ['You confirmed this report', 'तपाईंले यो उजुरी पुष्टि गर्नुभयो'],
  'corroborate.disputed': ['You objected to this report', 'तपाईंले आपत्ति जनाउनुभयो'],

  'nearby.title': ['Reports near you', 'तपाईं नजिकका उजुरी'],
  'nearby.hint': [
    'Confirm a neighbour’s report so the ward office knows it is real.',
    'छिमेकीको उजुरी पुष्टि गर्नुहोस् ताकि वडा कार्यालयलाई थाहा होस्।',
  ],
  'nearby.none': ['No open reports nearby.', 'नजिकै कुनै खुला उजुरी छैन।'],
  'nearby.scopeLabel': ['Which reports to show', 'कुन उजुरी देखाउने'],
  'nearby.tabNearby': ['Around me', 'मेरो वरिपरि'],
  'nearby.tabWard': ['My ward', 'मेरो वडा'],
  'nearby.wardTitle': ['Reports in my ward', 'मेरो वडाका उजुरी'],
  'nearby.wardHint': [
    'Everything your neighbours reported at home, wherever you are right now.',
    'तपाईं जहाँ भए पनि, आफ्नो वडामा छिमेकीले गरेका सबै उजुरी।',
  ],
  'nearby.wardNone': ['No reports in your ward yet.', 'तपाईंको वडामा अहिलेसम्म उजुरी छैन।'],

  'services.title': ['Civic services', 'नागरिक सेवाहरू'],
  'services.search': ['Search services', 'सेवा खोज्नुहोस्'],
  'services.all': ['All', 'सबै'],
  'services.hospital': ['Hospital', 'अस्पताल'],
  'services.ambulance': ['Ambulance', 'एम्बुलेन्स'],
  'services.police': ['Police', 'प्रहरी'],
  'services.fire': ['Fire', 'दमकल'],
  'services.ward_office': ['Ward office', 'वडा कार्यालय'],
  'services.municipality_office': ['Municipality', 'नगरपालिका'],
  'services.shelter': ['Shelter', 'आश्रय'],
  'services.pharmacy': ['Pharmacy', 'फार्मेसी'],
  'services.other': ['Other', 'अन्य'],
  'services.call': ['Call', 'फोन गर्नुहोस्'],
  'services.open24': ['Open 24 hours', '२४ घण्टा खुला'],
  'services.none': ['No services found.', 'कुनै सेवा भेटिएन।'],

  'sos.title': ['Emergency SOS', 'आपतकालीन SOS'],
  'sos.hint': [
    'This alerts your ward authority with your location. For immediate danger, call the numbers below.',
    'यसले तपाईंको स्थानसहित वडा अधिकारीलाई सूचित गर्छ। तत्काल खतरामा तलका नम्बरमा फोन गर्नुहोस्।',
  ],
  'sos.type': ['What kind of emergency?', 'कस्तो आपतकाल?'],
  'sos.medical': ['Medical', 'स्वास्थ्य'],
  'sos.fire': ['Fire', 'आगलागी'],
  'sos.police': ['Police', 'प्रहरी'],
  'sos.disaster': ['Disaster', 'प्रकोप'],
  'sos.other': ['Other', 'अन्य'],
  'sos.note': ['What is happening? (optional)', 'के भइरहेको छ? (वैकल्पिक)'],
  'sos.send': ['Send SOS', 'SOS पठाउनुहोस्'],
  'sos.sending': ['Sending...', 'पठाउँदै...'],
  'sos.sent': ['Emergency request sent', 'आपतकालीन अनुरोध पठाइयो'],
  'sos.callNow': ['Call these numbers now', 'अहिले यी नम्बरमा फोन गर्नुहोस्'],
  'sos.myRequests': ['My emergency requests', 'मेरा आपतकालीन अनुरोध'],

  'alerts.title': ['Public alerts', 'सार्वजनिक सूचना'],
  'alerts.none': ['No active alerts.', 'कुनै सक्रिय सूचना छैन।'],
  'alerts.instructions': ['What to do', 'के गर्ने'],
  'alerts.info': ['Information', 'जानकारी'],
  'alerts.warning': ['Warning', 'चेतावनी'],
  'alerts.critical': ['Critical', 'अति जरुरी'],

  'dashboard.title': ['Ward dashboard', 'वडा ड्यासबोर्ड'],
  'dashboard.open': ['Open reports', 'खुला उजुरी'],
  'dashboard.pendingReview': ['Awaiting duplicate review', 'नक्कल समीक्षा बाँकी'],
  'dashboard.openSos': ['Open emergencies', 'खुला आपतकाल'],
  'dashboard.resolved': ['Resolved', 'समाधान भएको'],
  'dashboard.allReports': ['All reports', 'सबै उजुरी'],
  'dashboard.filterAll': ['All', 'सबै'],

  'review.title': ['Possible duplicates', 'सम्भावित नक्कल'],
  'review.hint': [
    'The model suggests these are the same problem. Nothing is merged until you say so.',
    'मोडेलले यी एउटै समस्या हुन् भन्ने सुझाव दिएको छ। तपाईंले नभनेसम्म केही मर्ज हुँदैन।',
  ],
  'review.newReport': ['New report', 'नयाँ उजुरी'],
  'review.existingTicket': ['Existing ticket', 'विद्यमान टिकट'],
  'review.why': ['Why it matched', 'किन मिल्यो'],
  'review.merge': ['Same problem — merge', 'एउटै समस्या — मर्ज'],
  'review.dismiss': ['Different problems', 'फरक समस्या'],
  'review.none': ['Nothing to review.', 'समीक्षा गर्न केही छैन।'],
  'review.confidence': ['Match score', 'मिलान अंक'],

  'manage.updateStatus': ['Update status', 'अवस्था परिवर्तन'],
  'manage.note': ['Note (optional)', 'टिप्पणी (वैकल्पिक)'],
  'manage.resolutionNote': ['How was it resolved?', 'कसरी समाधान भयो?'],
  'manage.split': ['Split out from parent', 'अभिभावकबाट अलग गर्नुहोस्'],
  'manage.duplicateOf': ['Duplicate of', 'यसको नक्कल'],
  'manage.setPriority': ['Priority', 'प्राथमिकता'],
  'manage.wrongWard': ['Wrong ward?', 'गलत वडा?'],
  'manage.reassignWard': ['Move to another ward', 'अर्को वडामा सार्नुहोस्'],
  'manage.reassignHint': [
    'GPS routed this here. If it belongs to a neighbouring ward, move it — you will lose access once you do.',
    'GPS ले यहाँ पठायो। छिमेकी वडाको हो भने सार्नुहोस् — सारेपछि तपाईंको पहुँच रहँदैन।',
  ],

  'sosQueue.title': ['Emergency requests', 'आपतकालीन अनुरोध'],
  'sosQueue.acknowledge': ['Acknowledge', 'स्वीकार'],
  'sosQueue.dispatch': ['Dispatch help', 'सहयोग पठाउनुहोस्'],
  'sosQueue.close': ['Close', 'बन्द गर्नुहोस्'],
  'sosQueue.none': ['No emergency requests.', 'कुनै आपतकालीन अनुरोध छैन।'],

  'publish.title': ['Publish a public alert', 'सार्वजनिक सूचना जारी गर्नुहोस्'],
  'publish.titleEn': ['Title (English)', 'शीर्षक (अंग्रेजी)'],
  'publish.titleNe': ['Title (Nepali)', 'शीर्षक (नेपाली)'],
  'publish.bodyEn': ['Message (English)', 'सन्देश (अंग्रेजी)'],
  'publish.bodyNe': ['Message (Nepali)', 'सन्देश (नेपाली)'],
  'publish.instructions': ['Safety instructions', 'सुरक्षा निर्देशन'],
  'publish.severity': ['Severity', 'गम्भीरता'],
  'publish.target': ['Who should see this?', 'कसले हेर्ने?'],
  'publish.targetWard': ['Specific wards', 'निश्चित वडाहरू'],
  'publish.targetRadius': ['Area around a point', 'एक बिन्दु वरिपरि'],
  'publish.radius': ['Radius (metres)', 'त्रिज्या (मिटर)'],
  'publish.expires': ['Expires at', 'म्याद सकिने'],
  'publish.submit': ['Publish alert', 'सूचना जारी गर्नुहोस्'],
  'publish.published': ['Alert published', 'सूचना जारी भयो'],

  'approvals.title': ['Authority approvals', 'अधिकारी स्वीकृति'],
  'approvals.hint': [
    'These accounts cannot sign in until you approve them.',
    'स्वीकृत नभएसम्म यी खाताले साइन इन गर्न सक्दैनन्।',
  ],
  'approvals.approve': ['Approve', 'स्वीकृत'],
  'approvals.reject': ['Reject', 'अस्वीकृत'],
  'approvals.none': ['No accounts awaiting approval.', 'स्वीकृति पर्खिरहेको खाता छैन।'],
  'approvals.reason': ['Reason for rejection', 'अस्वीकृतिको कारण'],

  'a11y.language': ['भाषा / Language', 'भाषा / Language'],
  'a11y.largeText': ['Large text', 'ठूलो अक्षर'],
  'a11y.highContrast': ['High contrast', 'उच्च कन्ट्रास्ट'],
  'a11y.listen': ['Listen', 'सुन्नुहोस्'],
  'a11y.stop': ['Stop', 'रोक्नुहोस्'],
  'a11y.settings': ['Display settings', 'प्रदर्शन सेटिङ'],

  'common.save': ['Save', 'सुरक्षित'],
  'common.cancel': ['Cancel', 'रद्द'],
  'common.delete': ['Delete', 'मेट्नुहोस्'],
  'common.loading': ['Loading...', 'लोड हुँदै...'],
  'common.retry': ['Try again', 'फेरि प्रयास'],
  'common.back': ['Back', 'पछाडि'],
  'common.away': ['away', 'टाढा'],
  'common.optional': ['optional', 'वैकल्पिक'],
  'common.error': ['Something went wrong.', 'केही गडबड भयो।'],
  'common.viewAll': ['View all', 'सबै हेर्नुहोस्'],
  'common.search': ['Search', 'खोज्नुहोस्'],

  'pwa.installTitle': ['Install Sahayatri', 'सहयात्री इन्स्टल गर्नुहोस्'],
  'pwa.installBody': [
    'Add it to your home screen for faster access and offline emergency numbers.',
    'छिटो पहुँच र अफलाइन आपतकालीन नम्बरका लागि होम स्क्रिनमा थप्नुहोस्।',
  ],
  'pwa.install': ['Install', 'इन्स्टल'],
  'pwa.updateReady': ['A new version is ready.', 'नयाँ संस्करण तयार छ।'],
  'pwa.reload': ['Reload', 'पुनः लोड'],
  'pwa.offline': [
    'You are offline. Emergency numbers still work; new reports need a connection.',
    'तपाईं अफलाइन हुनुहुन्छ। आपतकालीन नम्बर चल्छ; नयाँ उजुरीलाई इन्टरनेट चाहिन्छ।',
  ],
} as const

export type StringKey = keyof typeof STRINGS

type I18nValue = {
  language: Language
  setLanguage: (language: Language) => void
  t: (key: StringKey) => string
  /** Pick the right field from an object that carries both languages. */
  pick: (en: string | null | undefined, ne: string | null | undefined) => string
}

const I18nContext = createContext<I18nValue | null>(null)
const STORAGE_KEY = 'sahayatri.language'

function readStored(): Language {
  try {
    const stored = localStorage.getItem(STORAGE_KEY)
    if (stored === 'ne' || stored === 'en') return stored
  } catch {
    // Fall through to the default.
  }
  return 'en'
}

export function I18nProvider({ children }: { children: ReactNode }) {
  const [language, setLanguageState] = useState<Language>(readStored)

  const setLanguage = useCallback((next: Language) => {
    setLanguageState(next)
    try {
      localStorage.setItem(STORAGE_KEY, next)
    } catch {
      // Preference just will not persist.
    }
  }, [])

  useEffect(() => {
    document.documentElement.lang = language
  }, [language])

  const value = useMemo<I18nValue>(
    () => ({
      language,
      setLanguage,
      t: (key) => {
        const entry = STRINGS[key]
        if (!entry) return key
        return language === 'ne' ? entry[1] || entry[0] : entry[0]
      },
      pick: (en, ne) => (language === 'ne' ? ne || en || '' : en || ne || ''),
    }),
    [language, setLanguage],
  )

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>
}

export function useI18n(): I18nValue {
  const context = useContext(I18nContext)
  if (!context) throw new Error('useI18n must be used inside I18nProvider')
  return context
}
