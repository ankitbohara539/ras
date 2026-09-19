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
  'nav.civic': ['Civic sense', 'नागरिक चेतना'],
  'nav.civicQueue': ['Civic complaints', 'नागरिक उजुरी'],
  'nav.safeRoute': ['Hazard map', 'खतरा नक्सा'],

  'hazard.title': ['Hazard map & safer routes', 'खतरा नक्सा र सुरक्षित बाटो'],
  'hazard.subtitle': [
    'Flooded or blocked roads, unsafe electrical areas, dark streets, broken footpaths and alert areas, with a route around them.',
    'डुबान वा अवरुद्ध सडक, असुरक्षित बिजुली, अँध्यारो बाटो, बिग्रिएको फुटपाथ र चेतावनी क्षेत्र, र तिनलाई छल्ने बाटो।',
  ],
  'hazard.disclaimer': [
    'Hazards come from citizen reports and official alerts, and conditions change quickly. A suggested route avoids reported hazards; it is not guaranteed safe. Use your own judgement.',
    'खतराहरू नागरिक उजुरी र आधिकारिक सूचनाबाट आउँछन्, र अवस्था छिट्टै बदलिन्छ। सुझाइएको बाटोले रिपोर्ट भएका खतरा छल्छ; सुरक्षित हुने ग्यारेन्टी छैन। आफ्नो विवेक प्रयोग गर्नुहोस्।',
  ],
  'hazard.mode': ['How are you travelling?', 'कसरी यात्रा गर्दै हुनुहुन्छ?'],
  'hazard.mode.walk': ['Walking', 'पैदल'],
  'hazard.mode.wheelchair': ['Wheelchair', 'ह्वीलचेयर'],
  'hazard.mode.drive': ['Vehicle', 'सवारी'],
  'hazard.from': ['From', 'बाट'],
  'hazard.to': ['To', 'सम्म'],
  'hazard.myLocation': ['My location', 'मेरो स्थान'],
  'hazard.noLocation': ['Location unavailable: set the start on the map', 'स्थान उपलब्ध छैन: नक्सामा सुरु बिन्दु राख्नुहोस्'],
  'hazard.pointOnMap': ['Point on the map', 'नक्साको बिन्दु'],
  'hazard.setStartOnMap': ['Set start on map', 'नक्सामा सुरु राख्नुहोस्'],
  'hazard.useMyLocation': ['Use my location', 'मेरो स्थान प्रयोग गर्नुहोस्'],
  'hazard.searchPlaceholder': ['Search a place, e.g. Ratna Park', 'ठाउँ खोज्नुहोस्, जस्तै रत्नपार्क'],
  'hazard.tapStart': ['Tap the map to set the start.', 'सुरु बिन्दु राख्न नक्सामा थिच्नुहोस्।'],
  'hazard.tapEnd': ['Tap the map, or search, to choose where you are going.', 'कहाँ जाने छान्न नक्सामा थिच्नुहोस् वा खोज्नुहोस्।'],
  'hazard.nightMode': ['Night: dark streets count as hazards', 'रात: अँध्यारो बाटो खतरा मानिन्छ'],
  'hazard.findRoute': ['Find a safer route', 'सुरक्षित बाटो खोज्नुहोस्'],
  'hazard.finding': ['Finding a route...', 'बाटो खोज्दै...'],
  'hazard.saferFound': ['Suggested route avoids reported hazards', 'सुझाइएको बाटोले रिपोर्ट भएका खतरा छल्छ'],
  'hazard.usualRoute': ['Suggested route', 'सुझाइएको बाटो'],
  'hazard.avoided': ['Avoided', 'छलिएका'],
  'hazard.stillOnRoute': ['Still on the way: take care', 'बाटोमै छन्: होसियार हुनुहोस्'],
  'hazard.greyIsUsual': ['Grey dashed line: the usual route', 'खैरो धर्का: सामान्य बाटो'],
  'hazard.legend': ['On this map', 'यो नक्सामा'],
  'hazard.sevHigh': ['serious', 'गम्भीर'],
  'hazard.sevMedium': ['moderate', 'मध्यम'],
  'hazard.sevLow': ['minor', 'सामान्य'],
  'hazard.reportHint': [
    'See a hazard that is not here? Report it: it appears on this map for everyone.',
    'यहाँ नभएको खतरा देख्नुभयो? रिपोर्ट गर्नुहोस्: यो सबैका लागि यही नक्सामा देखिन्छ।',
  ],

  'civic.title': ['Report civic misconduct', 'नागरिक अनुशासन उल्लङ्घन रिपोर्ट'],
  'civic.subtitle': [
    'Saw someone littering, dumping waste or blocking the footpath? Tell the ward office.',
    'कसैले फोहोर फालेको, थुप्रो लगाएको वा फुटपाथ ओगटेको देख्नुभयो? वडा कार्यालयलाई जानकारी दिनुहोस्।',
  ],
  'civic.newTab': ['New complaint', 'नयाँ उजुरी'],
  'civic.mineTab': ['My complaints', 'मेरा उजुरीहरू'],
  'civic.noneYet': ['You have not filed any civic complaints.', 'तपाईंले कुनै नागरिक उजुरी दिनुभएको छैन।'],
  'civic.rulesTitle': ['Before you report', 'रिपोर्ट गर्नुअघि'],
  'civic.rulePhotoAct': [
    'Photograph the act (the rubbish, the vehicle, the damage), not the person\'s face where you can avoid it.',
    'सकेसम्म व्यक्तिको अनुहार होइन, कार्य (फोहोर, गाडी, क्षति) को फोटो खिच्नुहोस्।',
  ],
  'civic.ruleSafety': [
    'Do not confront anyone or put yourself at risk to get a photo.',
    'फोटो खिच्न कसैसँग झगडा नगर्नुहोस् वा आफूलाई जोखिममा नपार्नुहोस्।',
  ],
  'civic.ruleChildren': ['Never photograph children.', 'बालबालिकाको फोटो कहिल्यै नखिच्नुहोस्।'],
  'civic.rulePrivate': [
    'Only the ward office sees your report and photo. It is never shown publicly.',
    'तपाईंको उजुरी र फोटो वडा कार्यालयले मात्र देख्छ। यो कहिल्यै सार्वजनिक हुँदैन।',
  ],
  'civic.ruleFalse': [
    'False or malicious reports may lead to action against the reporter.',
    'झूटा वा दुर्भावनापूर्ण उजुरीमा उजुरीकर्तामाथि कारबाही हुन सक्छ।',
  ],
  'civic.whatHappened': ['What happened?', 'के भयो?'],
  'civic.pickCategory': ['Choose what happened.', 'के भयो छान्नुहोस्।'],
  'civic.group.waste': ['Littering / dumping', 'फोहोर फाल्ने / थुपार्ने'],
  'civic.group.nuisance': ['Public nuisance', 'सार्वजनिक उपद्रव'],
  'civic.group.obstruction': ['Parking / encroachment', 'पार्किङ / अतिक्रमण'],
  'civic.group.damage': ['Vandalism / pet waste', 'तोडफोड / पाल्तु जनावरको फोहोर'],
  'civic.cat.littering': ['Littering', 'फोहोर फाल्नु'],
  'civic.cat.dumping_waste': ['Dumping waste (river, empty plot)', 'फोहोर थुपार्नु (खोला, खाली जग्गा)'],
  'civic.cat.burning_waste': ['Burning waste', 'फोहोर जलाउनु'],
  'civic.cat.spitting': ['Spitting', 'थुक्नु'],
  'civic.cat.public_urination': ['Public urination', 'सार्वजनिक स्थानमा पिसाब'],
  'civic.cat.smoking_in_public': ['Smoking in a no-smoking area', 'धूम्रपान निषेधित क्षेत्रमा धूम्रपान'],
  'civic.cat.noise': ['Loud noise at night', 'राति चर्को आवाज'],
  'civic.cat.illegal_parking': ['Illegal parking / blocking the road', 'अवैध पार्किङ / बाटो अवरोध'],
  'civic.cat.footpath_encroachment': ['Taking over the footpath', 'फुटपाथ अतिक्रमण'],
  'civic.cat.vandalism': ['Vandalism / graffiti', 'तोडफोड / भित्ते लेखन'],
  'civic.cat.pet_waste': ['Pet waste not cleaned up', 'पाल्तु जनावरको फोहोर नसफा गर्नु'],
  'civic.cat.other': ['Something else', 'अन्य'],
  'civic.describe': ['Describe what you saw', 'के देख्नुभयो वर्णन गर्नुहोस्'],
  'civic.describeHint': [
    'What happened, and anything that helps identify it: a shop name, a vehicle number.',
    'के भयो, र पहिचान गर्न मद्दत गर्ने कुरा: पसलको नाम, सवारी नम्बर।',
  ],
  'civic.when': ['When did it happen?', 'कहिले भयो?'],
  'civic.happened': ['Happened', 'भएको'],
  'civic.photos': ['Photo evidence', 'फोटो प्रमाण'],
  'civic.photosHint': ['At least one photo, up to 3.', 'कम्तीमा एउटा, बढीमा ३ फोटो।'],
  'civic.photoRequired': ['Add at least one photo of what happened.', 'कम्तीमा एउटा फोटो थप्नुहोस्।'],
  'civic.where': ['Where did it happen?', 'कहाँ भयो?'],
  'civic.goesTo': ['Goes to', 'यसमा जान्छ'],
  'civic.acknowledge': [
    'I saw this myself, and this report is true to the best of my knowledge.',
    'मैले यो आफैं देखेँ, र मेरो जानकारीअनुसार यो उजुरी सत्य हो।',
  ],
  'civic.submit': ['Send to ward office', 'वडा कार्यालयमा पठाउनुहोस्'],
  'civic.filed': ['Complaint sent:', 'उजुरी पठाइयो:'],
  'civic.filedNote': [
    'You will be notified when the ward office acts on it. Sent to',
    'वडा कार्यालयले कारबाही गरेपछि तपाईंलाई सूचना आउनेछ। पठाइएको:',
  ],
  'civic.officeSaid': ['Ward office response', 'वडा कार्यालयको जवाफ'],
  'civic.evidence': ['Photo evidence', 'फोटो प्रमाण'],
  'civic.status.submitted': ['Received', 'प्राप्त'],
  'civic.status.under_review': ['Under review', 'समीक्षामा'],
  'civic.status.action_taken': ['Action taken', 'कारबाही भयो'],
  'civic.status.dismissed': ['Dismissed', 'खारेज'],

  'civicQueue.title': ['Civic complaints', 'नागरिक उजुरी'],
  'civicQueue.subtitle': [
    'Reports of people littering, dumping, blocking footpaths and similar. Private: not visible to other citizens.',
    'फोहोर फाल्ने, फुटपाथ ओगट्ने जस्ता व्यक्तिगत आचरणका उजुरी। निजी: अरू नागरिकले देख्दैनन्।',
  ],
  'civicQueue.all': ['All', 'सबै'],
  'civicQueue.empty': ['No complaints here.', 'यहाँ कुनै उजुरी छैन।'],
  'civicQueue.reportedBy': ['Reported by', 'उजुरीकर्ता'],
  'civicQueue.showMap': ['Show on map', 'नक्सामा हेर्नुहोस्'],
  'civicQueue.hideMap': ['Hide map', 'नक्सा लुकाउनुहोस्'],
  'civicQueue.note': ['Note to the reporter', 'उजुरीकर्तालाई टिप्पणी'],
  'civicQueue.noteHint': [
    'Required to close: say what was done, or why no action was taken.',
    'बन्द गर्न आवश्यक: के गरियो वा किन कारबाही भएन भन्नुहोस्।',
  ],
  'civicQueue.notePlaceholder': ['e.g. Warned the shop owner; fined Rs 500', 'जस्तै: पसलेलाई चेतावनी; रु ५०० जरिवाना'],
  'civicQueue.noteRequired': [
    'Write a note first: the reporter is told what happened.',
    'पहिले टिप्पणी लेख्नुहोस्: उजुरीकर्तालाई के भयो भनिन्छ।',
  ],
  'civicQueue.to.under_review': ['Start review', 'समीक्षा सुरु'],
  'civicQueue.to.action_taken': ['Mark action taken', 'कारबाही भयो'],
  'civicQueue.to.dismissed': ['Dismiss', 'खारेज गर्नुहोस्'],
  'nav.notifications': ['Notifications', 'सूचनाहरू'],
  'notifications.markAllRead': ['Mark all read', 'सबै पढिएको बनाउनुहोस्'],
  'nav.logout': ['Sign out', 'साइन आउट'],
  'nav.menu': ['Menu', 'मेनु'],

  'auth.login': ['Sign in', 'साइन इन'],
  'auth.register': ['Create account', 'खाता खोल्नुहोस्'],
  'auth.email': ['Email', 'इमेल'],
  'auth.password': ['Password', 'पासवर्ड'],
  'auth.fullName': ['Full name', 'पूरा नाम'],
  'auth.phone': ['Phone number', 'फोन नम्बर'],
  'auth.noAccount': ['New here?', 'नयाँ हुनुहुन्छ?'],
  'auth.checkInbox': ['Check your email', 'आफ्नो इमेल हेर्नुहोस्'],
  'auth.thenApproval': [
    'After verifying, an administrator still has to approve officer accounts before they can sign in.',
    'इमेल प्रमाणित गरेपछि पनि अधिकारी खाता प्रशासकले स्वीकृत गरेपछि मात्र साइन इन गर्न मिल्छ।',
  ],
  'auth.resendVerification': ['Resend verification email', 'प्रमाणीकरण इमेल फेरि पठाउनुहोस्'],
  'auth.sending': ['Sending...', 'पठाउँदै...'],
  'auth.checkSpam': [
    'Not in your inbox? Check the spam or promotions folder.',
    'इनबक्समा छैन? स्प्याम वा प्रमोसन फोल्डर हेर्नुहोस्।',
  ],
  'auth.verified': [
    'Email verified. Sign in to continue.',
    'इमेल प्रमाणित भयो। जारी राख्न साइन इन गर्नुहोस्।',
  ],
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
  'report.address': ['Place name / nearby landmark', 'ठाउँको नाम / नजिकको चिनारी'],
  'report.addressHint': [
    'Filled in from the map pin. Add a landmark if it helps the crew find it.',
    'नक्साको पिनबाट आफैं भरिन्छ। टोलीलाई सजिलो होस् भने चिनारी थप्नुहोस्।',
  ],
  'report.pinHint': [
    'Drag the red pin, or tap the map, to mark exactly where the problem is.',
    'समस्या भएको ठ्याक्कै ठाउँमा रातो पिन तान्नुहोस् वा नक्सामा थिच्नुहोस्।',
  ],
  'report.refining': ['Improving GPS accuracy...', 'GPS सटीकता सुधार्दै...'],
  'report.lowAccuracy': [
    'Your device only knows your location roughly. Please move the pin to the exact spot.',
    'तपाईंको उपकरणले स्थान अन्दाजी मात्र दिएको छ। कृपया पिन ठ्याक्कै ठाउँमा सार्नुहोस्।',
  ],
  'report.pinnedByHand': ['Placed by you', 'तपाईंले राख्नुभएको'],
  'report.coordinates': ['Coordinates', 'निर्देशांक'],
  'report.placeName': ['Place', 'ठाउँ'],
  'report.findingPlace': ['Finding place name...', 'ठाउँको नाम खोज्दै...'],
  'report.backToGps': ['Use GPS again', 'फेरि GPS प्रयोग गर्नुहोस्'],
  'report.autoMerged': [
    'Someone already reported this problem, so your report was added to theirs',
    'यो समस्या पहिले नै कसैले रिपोर्ट गरिसकेकोले तपाईंको उजुरी त्यसमा जोडियो',
  ],
  'report.autoMergedNote': [
    'Your voice counts: more reporters raise its priority, and you will be notified when it is fixed.',
    'तपाईंको आवाज गनिन्छ: धेरै रिपोर्टकर्ताले प्राथमिकता बढाउँछ, र समाधान भएपछि तपाईंलाई सूचना आउनेछ।',
  ],
  'report.viewMain': ['View the main report', 'मुख्य उजुरी हेर्नुहोस्'],
  'report.viewReport': ['View report', 'उजुरी हेर्नुहोस्'],
  'report.reportN': ['Report', 'उजुरी'],
  'report.remove': ['Remove', 'हटाउनुहोस्'],
  'report.addAnother': ['Add another report', 'अर्को उजुरी थप्नुहोस्'],
  'report.addAnotherHint': [
    'Found more than one problem? Add each as its own report and submit them together.',
    'एकभन्दा बढी समस्या भेट्नुभयो? प्रत्येकलाई छुट्टै उजुरीको रूपमा थपेर सँगै पेश गर्नुहोस्।',
  ],
  'report.sameSpotHint': [
    'Starts at the same spot as the previous report. Move the pin if this one is somewhere else.',
    'अघिल्लो उजुरीकै ठाउँबाट सुरु हुन्छ। यो अर्कै ठाउँमा छ भने पिन सार्नुहोस्।',
  ],
  'report.submitAll': ['Submit all reports', 'सबै उजुरी पेश गर्नुहोस्'],
  'report.submittedMany': ['Reports submitted', 'उजुरीहरू पेश भए'],
  'report.reportAnother': ['Report something else', 'अर्को समस्या रिपोर्ट गर्नुहोस्'],
  'report.someFailed': [
    'Some reports could not be submitted. They are still below; fix them and submit again.',
    'केही उजुरी पेश हुन सकेनन्। ती तल नै छन्; मिलाएर फेरि पेश गर्नुहोस्।',
  ],
  'report.alreadyFiled': ['Already submitted', 'पेश भइसकेका'],
  'ticket.openInMaps': ['Open in Maps', 'नक्सामा खोल्नुहोस्'],
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
    'Set automatically from category severity, how many people reported it, how many ask for it to be fixed in the comments, and how long it has gone unresolved.',
    'श्रेणीको गम्भीरता, कति जनाले उजुरी गरे, टिप्पणीमा कति जनाले समाधान मागे र कति समयदेखि समाधान भएको छैन भन्ने आधारमा स्वतः तय हुन्छ।',
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
  'comments.urgent': ['Wants it fixed', 'समाधान माग'],
  'comments.urgentHint': [
    'When 3 or more people ask for this to be fixed or complain about it, its priority goes up (6 people: up two levels).',
    '३ वा बढी जनाले समाधान मागेमा वा गुनासो गरेमा प्राथमिकता बढ्छ (६ जना: दुई तह)।',
  ],
  'comments.urgentCount': ['people want this fixed', 'जनाले समाधान माग्नुभयो'],
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
  'dashboard.allWards': ['all wards', 'सबै वडा'],
  'dashboard.allMunicipalities': ['All municipalities', 'सबै नगरपालिका'],
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
  'common.close': ['Close', 'बन्द गर्नुहोस्'],

  'summary.citizenCardTitle': ['Your briefing', 'तपाईंको विवरण'],
  'summary.citizenCardHint': [
    'A quick summary of your reports and what is happening in your ward.',
    'तपाईंका उजुरी र वडामा भइरहेको कुराको छोटो सारांश।',
  ],
  'summary.officerCardTitle': ['Ward briefing', 'वडा विवरण'],
  'summary.officerCardHint': [
    'A quick summary of your queue: what needs attention first.',
    'तपाईंको काम सूचीको छोटो सारांश: पहिले केमा ध्यान दिने।',
  ],
  'summary.buttonLabel': ['Get my briefing', 'मेरो विवरण हेर्नुहोस्'],
  'summary.title': ['Your briefing', 'तपाईंको विवरण'],
  'summary.yourOpen': ['Open reports', 'खुला उजुरी'],
  'summary.yourTotal': ['Total reports', 'कुल उजुरी'],
  'summary.wardOpen': ['Open in your ward', 'तपाईंको वडामा खुला'],
  'summary.needsAttention': ['Need attention', 'ध्यान चाहिने'],
  'summary.oldestOpen': ['Oldest open', 'सबैभन्दा पुरानो खुला'],
  'summary.days': ['days', 'दिन'],
  'summary.pendingDuplicates': ['Duplicates to review', 'नक्कल समीक्षा बाँकी'],
  'summary.openSos': ['Open SOS', 'खुला आपतकाल'],
  'summary.pendingCivic': ['Civic complaints waiting', 'नागरिक उजुरी बाँकी'],
  'summary.wardIssuesTitle': [
    'Issues needing attention in your ward',
    'तपाईंको वडामा ध्यान चाहिने समस्या',
  ],
  'summary.attentionIssuesTitle': ['Needs your attention', 'तपाईंको ध्यान चाहिन्छ'],
  'summary.colReport': ['Report', 'उजुरी'],
  'summary.colReporters': ['Reporters', 'रिपोर्टकर्ता'],
  'summary.colAge': ['Age', 'उमेर'],
  'summary.regenerate': ['Regenerate', 'फेरि बनाउनुहोस्'],
  'summary.regenerating': ['Regenerating...', 'फेरि बनाउँदै...'],
  'summary.tooSoon': [
    'Give it a moment before asking again.',
    'फेरि सोध्नु अघि केही समय पर्खनुहोस्।',
  ],
  'summary.noAiNote': [
    'Built from your data -- AI writing is temporarily unavailable.',
    'तपाईंको डेटाबाट बनाइएको -- AI लेखन अस्थायी रूपमा अनुपलब्ध छ।',
  ],
  'summary.aiWritten': ['AI-written', 'AI-लिखित'],
  'summary.thinking': ['Looking through your ward…', 'तपाईंको वडा हेर्दै…'],

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
