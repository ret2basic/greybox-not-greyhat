import type { Metadata } from 'next'

import { LegalPage } from '@/components/shared/LegalPage'

export const metadata: Metadata = {
  title: 'Privacy Policy | DAWN',
  description:
    'Read the Universal Privacy Policy describing how the DAWN and Andrena ecosystem entities collect, use, disclose, process, and protect personal information.',
}

const PrivacyPolicyPage = () => {
  return (
    <LegalPage title='Privacy Policy' meta='Effective Date: May 12, 2026'>
      <h3>
        <strong>1. Overview</strong>
      </h3>
      <p>
        This Privacy Policy describes how certain entities within the broader DAWN and Andrena
        ecosystem collect, use, disclose, process, and protect personal information in connection
        with the Services. Depending on the Services you access or interact with, personal
        information may be processed by one or more independent entities, including DAWN Ops Ltd.,
        DAWN Foundation, DAWN TokenCo Ltd., or related token administration entities; Andrena, Inc.,
        Andrena Holdings, LLC and its affiliated Series entities (“<strong>SPVs</strong>”), and
        affiliated operational, administrative, servicing, governance, or support entities
        (collectively, for convenience, “<strong>DAWN</strong>,” “<strong>we</strong>,” “
        <strong>us</strong>,” or “<strong>our</strong>”).
      </p>
      <p>
        These entities may perform different functions within the broader ecosystem, including
        operation of applications, dashboards, interfaces, and related Services; protocol stewardship
        and ecosystem coordination; technical token-related support functions; infrastructure
        deployment and servicing; telecommunications operations; and infrastructure-related
        ownership, operational, administrative, or contractual functions. Depending on the context
        and applicable law, different entities may act as independent data controllers; joint
        controllers; processors; service providers; or operational counterparties.
      </p>
      <p>This Privacy Policy applies when you access or use:</p>
      <ul role='list'>
        <li>
          <a href='https://dawninternet.com'>https://dawninternet.com</a>;
        </li>
        <li>
          <a href='https://andrena.com'>https://andrena.com</a>;
        </li>
        <li>
          usd.tel, app.usd.tel, and any related applications, dashboards, browser extensions, APIs,
          software, smart contracts, or successor domains operated by or on behalf of the DAWN
          ecosystem entities;
        </li>
        <li>smart contract integrations;</li>
        <li>Rewards Program interfaces;</li>
        <li>ecosystem incentive systems;</li>
        <li>protocol participation interfaces;</li>
        <li>InfraFi-related interfaces, dashboards, or informational systems;</li>
        <li>
          and other applications, technologies, or services that link to or reference this Privacy
          Policy
        </li>
      </ul>
      <p>
        (collectively, the “<strong>Services</strong>”).
      </p>
      <p>
        Certain Services may involve interaction with blockchain networks, smart contracts, digital
        wallets, decentralized systems, telecommunications infrastructure, third-party protocols,
        independent operators, or infrastructure-owning SPVs not directly controlled by DAWN. Certain
        Services or features may be subject to additional terms, eligibility requirements, geographic
        restrictions, onboarding procedures, or separate agreements. Finally, certain Services,
        interfaces, protocol features, or infrastructure-related systems may not be available in all
        jurisdictions and may be restricted based on legal, regulatory, sanctions, compliance, risk,
        or operational considerations.
      </p>

      <h3>
        <strong>2. Entities Covered and Roles</strong>
      </h3>
      <p>This Policy applies to the following entities:</p>
      <ul role='list'>
        <li>
          <strong>DAWN Foundation (Cayman Islands)</strong> – protocol governance and ecosystem
          coordination; and treasury and strategic oversight.
        </li>
        <li>
          <strong>DAWN Ops Ltd. (BVI)</strong> – application interfaces, dashboard integrations, and
          operations; and user-facing product functionality.
        </li>
        <li>
          <strong>DAWN Mint / TokenCo (BVI)</strong> – token minting, technical token administration,
          and protocol-related distribution support functions.
        </li>
        <li>
          <strong>Andrena, Inc. (US)</strong> – independent telecommunications infrastructure
          deployment, network operations and servicing; and commercial and operational relationships
          with property owners, vendors, and partners.
        </li>
        <li>
          <strong>Andrena Holdings, LLC and Series SPVs</strong> – ownership of
          infrastructure-related contracts, receivables, and associated assets; and independent
          operation of project-specific infrastructure entities. DAWN does not own, operate, or
          control infrastructure assets or Series SPVs. Series SPVs are not consumer-facing entities
          and generally do not directly interact with end users.
        </li>
      </ul>
      <p>
        Depending on the context, entities may act as independent data controllers. In limited cases,
        entities may act as joint controllers. Service providers act as data processors. Each entity
        processes personal data only as necessary for its respective role.
      </p>

      <h3>
        <strong>3. Scope of This Policy</strong>
      </h3>
      <p>
        This Policy applies when you access or use the Services, access InfraFi interfaces, interact
        with protocol participation systems, Rewards Programs, or InfraFi-related interfaces, or
        engage with Andrena services or infrastructure deployments. This Policy does{' '}
        <strong>not</strong> apply to third-party services not controlled by DAWN or publicly
        available blockchain data.
      </p>

      <h3>
        <strong>4. Information We Collect</strong>
      </h3>
      <p>
        DAWN and Andrena seek to limit collection of personal data to information reasonably
        necessary for operational, contractual, legal, security, compliance, telecommunications,
        infrastructure servicing, and business purposes. We collect the following categories of
        information:
      </p>
      <h4>4.1 Information You Provide</h4>
      <ul role='list'>
        <li>name, email address, service address</li>
        <li>billing information, billing address</li>
        <li>account credentials</li>
        <li>wallet addresses</li>
        <li>smart contract interaction identifiers</li>
        <li>blockchain account identifiers</li>
        <li>protocol interaction metadata</li>
        <li>communications (support requests, feedback)</li>
        <li>business or partner information (for Andrena services)</li>
      </ul>
      <h4>4.2 Technical Information</h4>
      <ul role='list'>
        <li>IP address</li>
        <li>device type, browser, operating system</li>
        <li>log data, timestamps</li>
        <li>network performance and usage data</li>
      </ul>
      <h4>4.3 Blockchain and Protocol Data</h4>
      <ul role='list'>
        <li>wallet addresses</li>
        <li>transaction hashes</li>
        <li>Rewards Program participation data</li>
        <li>protocol interaction activity</li>
        <li>smart contract interaction data</li>
        <li>vault interaction data (where applicable)</li>
        <li>protocol interaction data</li>
      </ul>
      <p>
        <strong>Note:</strong> Blockchain data is publicly visible and immutable.
      </p>
      <h4>4.4 InfraFi-Related Data</h4>
      <p>
        Where applicable, we may process wallet activity linked to InfraFi interfaces, interaction
        with protocol dashboards, and system-level participation metrics.
      </p>
      <p>
        Personal information may be shared between DAWN entities, including Andrena and affiliated
        entities, to operate the DAWN Services and support infrastructure operations, including
        infrastructure-owning special purpose vehicles and service providers, where necessary to
        support operational, technical, or contractual functions.
      </p>
      <p>
        Such entities operate independently and may process data in accordance with their own legal
        obligations. Certain data processing activities relate to protocol-level services, while
        others relate to infrastructure operations. These activities are distinct and may involve
        different entities within the DAWN and Andrena ecosystem.
      </p>
      <h4>4.5 Read-Only Access Data</h4>
      <p>
        We may also process limited compliance and access-control data used to determine
        jurisdictional eligibility, read-only access restrictions, sanctions screening, or feature
        availability.
      </p>
      <h4>4.6 Andrena Commercial and Operational Data</h4>
      <p>
        Andrena may collect property owner and partner contact details, site access and installation
        data, service and maintenance records, vendor and contractor information, and operational
        network performance data. In addition, Andrena, Inc. may collect operational and
        infrastructure-related information, including installation, service, and performance data,
        solely for purposes of providing infrastructure services.
      </p>
      <h4>4.7 Cookies and Tracking Data</h4>
      <p>We use cookies and similar technologies (see Section 10).</p>
      <h4>4.8 No Financial Account Data</h4>
      <p>
        DAWN does not generally collect traditional bank account credentials, brokerage credentials,
        or private wallet keys.
      </p>
      <h4>4.9 Sensitive Information</h4>
      <p>
        Unless specifically required for a particular Service, DAWN and Andrena generally request
        that users do not provide government-issued identification numbers, financial account
        credentials, private wallet keys, biometric information, precise geolocation information,
        health information, or other sensitive categories of information. Users should never share
        private keys, seed phrases, authentication credentials, or wallet recovery information with
        DAWN, Andrena, or any third party.
      </p>

      <h3>
        <strong>5. How We Use Information</strong>
      </h3>
      <h4>5.1 Personal Data</h4>
      <p>
        We use personal data to operate and maintain the Services, provide protocol functionality,
        application interfaces, and infrastructure coordination systems, support InfraFi interfaces
        (informational and technical functions only), provide protocol functionality, application
        interfaces, and infrastructure coordination systems, provide Andrena services and
        infrastructure operations, improve performance and user experience, communicate with users
        and partners, detect and prevent fraud or misuse, comply with legal obligations, conduct
        sanctions screening, fraud prevention, and jurisdictional access controls, and enforce
        feature restrictions and compliance-related eligibility requirements.
      </p>
      <p>
        Personal information may also be used to support infrastructure operations conducted by
        Andrena and its affiliated entities.
      </p>
      <h4>5.2 Legal Bases for Processing</h4>
      <p>
        To the extent applicable under the GDPR, UK GDPR, Swiss data protection laws, or similar
        laws, DAWN and Andrena process personal data pursuant to one or more of the following legal
        bases performance of a contract or steps taken prior to entering into a contract, compliance
        with legal obligations, legitimate interests, including operation of the Services, fraud
        prevention, network security, infrastructure management, protocol administration,
        telecommunications operations, analytics, and business operations, consent, where required by
        law, and protection of legal rights, security, safety, and operational integrity.
      </p>
      <p>
        Legitimate interests may include operating and improving the Services, supporting protocol
        and infrastructure systems, fraud detection and prevention, sanctions screening, network
        management, cybersecurity, infrastructure servicing, customer support, legal compliance, and
        protection of DAWN’s, Andrena’s, users’, counterparties’, and third parties’ rights and
        interests.
      </p>
      <p>
        Where consent is required by applicable law, users may withdraw consent at any time, subject
        to legal and operational limitations.
      </p>

      <h3>
        <strong>6. Entity-Specific Processing</strong>
      </h3>
      <h4>6.1 DAWN Foundation</h4>
      <p>
        Processes data for governance and coordination, ecosystem analytics, and ecosystem
        coordination, governance administration, analytics, and operational oversight.
      </p>
      <h4>6.2 DAWN Ops Ltd.</h4>
      <p>
        Processes data for application functionality, user interface operations, and integrations and
        platform performance.
      </p>
      <h4>6.3 TokenCo</h4>
      <p>
        Processes limited data strictly for technical support functions relating to token
        administration or protocol-related distributions, and smart contract interactions.
      </p>
      <h4>6.4 Andrena, Inc.</h4>
      <p>
        Processes data for infrastructure deployment and servicing, commercial relationships,
        customer relationships, operational performance and maintenance, and compliance with telecom
        and regulatory obligations.
      </p>
      <h4>6.5 Andrena Holdings and Series SPVs</h4>
      <p>
        Series SPVs may maintain operational and contractual records, and may process limited data
        related to infrastructure performance or contractual obligations. SPVs operate independently
        and do not provide user-facing services.
      </p>
      <h4>6.6 Marketing and Transactional Communications</h4>
      <p>
        DAWN and Andrena may send operational communications, transactional notices, onboarding
        communications, service-related announcements, security notifications, support
        communications, and, where permitted by law, marketing or promotional communications.
      </p>
      <p>
        Users may opt out of marketing communications at any time by using unsubscribe functionality
        or contacting DAWN or Andrena directly.
      </p>
      <p>
        Users may continue to receive operational, transactional, compliance, legal, security,
        onboarding, or account-related communications necessary for operation of the Services.
      </p>

      <h3>
        <strong>7. How We Share Information</strong>
      </h3>
      <p>
        DAWN and Andrena may share personal information, technical information, blockchain-related
        information, operational data, or other information as reasonably necessary to operate and
        maintain the Services; support protocol functionality and infrastructure systems; provide
        customer support; administer Rewards Programs or related interfaces; comply with legal and
        regulatory obligations; prevent fraud, abuse, sanctions violations, or security incidents;
        enforce contractual rights; support infrastructure deployment and servicing activities; and
        conduct operational, compliance, governance, security, analytics, or business functions.
        Information may be shared in the following circumstances:
      </p>
      <h4>7.1 Between DAWN Entities</h4>
      <p>
        Personal information may be shared between DAWN entities, including Andrena and affiliated
        entities, to operate the DAWN Services and support infrastructure operations; and affiliated
        operational, administrative, governance, servicing, or support entities.
      </p>
      <h4>7.2 With Service Providers</h4>
      <p>
        Information may be shared with cloud hosting providers, analytics providers, security and
        compliance vendors, and customer support systems. Service providers may process information
        only as reasonably necessary to provide services on behalf of DAWN or Andrena, subject to
        applicable contractual, legal, operational, security, or compliance restrictions.
      </p>
      <h4>7.3 With Regulators or Authorities</h4>
      <p>
        DAWN and Andrena may disclose information where required by applicable law, regulation,
        subpoena, court order, governmental request, or legal process; to comply with sanctions
        obligations, anti-money laundering obligations, fraud prevention requirements, or other
        compliance obligations; to protect the rights, safety, integrity, security, or property of
        DAWN, Andrena, users, counterparties, or third parties; to investigate suspected fraud,
        abuse, unauthorized access, security incidents, sanctions violations, or unlawful activity;
        or in connection with audits, examinations, investigations, litigation, dispute resolution,
        or regulatory inquiries.
      </p>
      <p>
        Information may also be shared with regulators; law enforcement; governmental agencies;
        sanctions-screening providers; blockchain monitoring providers; legal advisors; auditors;
        insurers; financing counterparties; trustees; and other compliance or operational
        counterparties where reasonably necessary.
      </p>
      <h4>7.4 With Business Counterparties and Infrastructure Participants</h4>
      <p>
        In connection with infrastructure operations, telecommunications activities, deployment
        services, servicing arrangements, or related operational functions, DAWN and Andrena may
        share information with property owners; landlords; utilities; telecommunications carriers;
        vendors; contractors; installers; infrastructure operators; maintenance providers; financing
        counterparties; infrastructure managers; servicing agents; and other operational or
        commercial counterparties.
      </p>
      <p>
        Such sharing may occur for purposes including infrastructure deployment; maintenance and
        servicing; operational coordination; contract administration; compliance; technical
        troubleshooting; billing and accounting; financing or servicing administration;
        infrastructure monitoring; and telecommunications operations.
      </p>
      <p>
        Certain infrastructure systems or contractual arrangements may involve independent SPVs or
        third-party entities operating separately from DAWN or Andrena.
      </p>
      <h4>7.5 Public Blockchain</h4>
      <p>
        Certain Services may involve interaction with public blockchain networks or decentralized
        systems. Blockchain transactions, wallet addresses, smart contract interactions, protocol
        activity, and related metadata may be publicly visible, immutable, permanently accessible,
        and independently indexed by third parties.
      </p>
      <p>
        DAWN and Andrena do not control public blockchain records; third-party blockchain indexing;
        decentralized storage systems; validator activity; blockchain explorers; or independent
        blockchain analytics providers.
      </p>
      <p>
        Users should understand that blockchain-related information may remain publicly accessible
        indefinitely and may be associated with wallet addresses, transaction history, protocol
        interactions, or related metadata.
      </p>
      <p>
        DAWN and Andrena do not sell personal information for monetary consideration. However, certain
        data-sharing activities involving analytics, compliance, infrastructure monitoring,
        advertising technologies, or blockchain-related systems may constitute “sharing” under certain
        laws depending on applicable legal interpretations.
      </p>
      <h4>7.6 Third-Party Protocols and Blockchain Systems</h4>
      <p>
        Certain Services may interact with or rely upon third-party blockchain networks; wallet
        providers; smart contract systems; decentralized protocols; validators; oracles; bridges;
        liquidity systems; blockchain analytics providers; compliance providers; decentralized
        applications; infrastructure coordination systems; or protocol-related technologies that are
        not owned, operated, administered, or controlled by DAWN or Andrena.
      </p>
      <p>
        Information transmitted to or through such systems may be processed independently by third
        parties pursuant to their own terms, privacy policies, operational practices, or legal
        obligations. DAWN and Andrena are not responsible for the privacy or security practices of
        third-party systems; blockchain functionality; wallet security; smart contract operation;
        validator conduct; protocol governance decisions; third-party data processing; or failures,
        outages, exploits, or vulnerabilities associated with third-party infrastructure. Users
        interact with third-party blockchain systems and wallet providers entirely at their own risk.
      </p>
      <h4>7.7 Corporate Transactions</h4>
      <p>
        Information may be disclosed or transferred in connection with mergers, acquisitions,
        financings, restructurings, reorganizations, insolvency proceedings, sales of assets,
        securitizations, infrastructure financings, servicing transfers, or other corporate or
        commercial transactions.
      </p>
      <p>
        Recipients may include counterparties, lenders, investors, trustees, servicers, professional
        advisors, insurers, auditors, and financing participants.
      </p>

      <h3>
        <strong>8. International Data Transfers</strong>
      </h3>
      <h4>8.1 International Transfer Safeguards</h4>
      <p>
        Where required by applicable law, DAWN and Andrena implement safeguards intended to protect
        personal data transferred internationally, including Standard Contractual Clauses (“
        <strong>SCCs</strong>”), contractual data protection obligations, technical and
        organizational safeguards, adequacy decisions, transfer impact assessments, and other legally
        recognized transfer mechanisms.
      </p>
      <p>
        Users acknowledge that personal data may be transferred to and processed in jurisdictions
        that may provide different levels of legal protection than their jurisdiction of residence.
      </p>

      <h3>
        <strong>9. Data Retention</strong>
      </h3>
      <p>
        We retain data only as long as necessary to provide Services, meet legal obligations, resolve
        disputes, and enforce agreements. Retention varies by data category. We retain personal data
        based on operational, legal, and compliance requirements. Retention periods vary depending on
        the type of data, including Account data: retained while account is active and for a
        reasonable period thereafter; Technical logs: typically retained up to 12 months;
        Compliance-related data: retained as required by law. Certain blockchain-related data,
        including public wallet addresses and blockchain transaction records, may remain publicly
        accessible indefinitely due to the nature of blockchain systems.
      </p>
      <p>
        DAWN and Andrena may also retain personal data to establish, exercise, or defend legal claims,
        comply with legal, accounting, telecommunications, tax, sanctions, or regulatory obligations,
        enforce agreements, conduct audits, maintain security and fraud prevention systems, and
        preserve business and operational records.
      </p>
      <p>
        Retention periods may vary depending on applicable legal requirements, operational needs,
        contractual obligations, infrastructure servicing requirements, dispute resolution needs, and
        the nature of the Services involved.
      </p>

      <h3>
        <strong>10. Cookies and Analytics</strong>
      </h3>
      <h4>10.1 Types of Cookies</h4>
      <ul role='list'>
        <li>Essential cookies</li>
        <li>Performance/analytics cookies</li>
        <li>Functional cookies</li>
        <li>Marketing cookies (where applicable)</li>
      </ul>
      <p>
        Users may control cookie preferences through browser settings or consent tools where
        available.
      </p>
      <h4>10.2 Analytics</h4>
      <p>
        We may use third-party analytics tools (e.g., Google Analytics) to understand usage, and
        improve Services. Analytics providers may include blockchain analytics, wallet-screening,
        sanctions-compliance, fraud-detection, or protocol monitoring providers.
      </p>
      <h4>10.3 Cookie Control and Consent Management</h4>
      <p>
        Users may manage or disable cookies and similar technologies through browser settings;
        device-level privacy controls; cookie consent banners or preference centers (where
        available); and industry-standard opt-out mechanisms.
      </p>
      <p>
        Most browsers permit users to review stored cookies; delete cookies; block third-party
        cookies; block all cookies; or receive notifications before cookies are placed. Disabling or
        restricting certain cookies may affect the availability, functionality, performance, or user
        experience of certain Services, interfaces, dashboards, or features.
      </p>
      <p>
        Certain Services may continue to use essential or strictly necessary cookies required for
        authentication; security; fraud prevention; network management; compliance; load balancing;
        session integrity; or operation of core functionality. In addition, certain third-party
        analytics, blockchain analytics, wallet-screening, compliance, fraud-detection, or
        infrastructure-monitoring providers may use cookies or similar technologies subject to their
        own privacy practices and terms. Users may also manage advertising and analytics preferences
        through industry-standard tools, browser extensions, or applicable platform privacy controls
        where available.
      </p>
      <h4>10.4 Global Privacy Control (GPC) and Browser Privacy Signals</h4>
      <p>
        Where required by applicable law, DAWN and Andrena recognize Global Privacy Control (“
        <strong>GPC</strong>”) signals and certain browser-based opt-out preference signals intended
        to communicate a user’s privacy preferences. Depending on applicable law and technical
        feasibility, recognized signals may be treated as requests to opt out of certain categories
        of data sharing or targeted advertising; limit certain tracking technologies; or apply privacy
        preference settings associated with the requesting browser or device.
      </p>
      <p>
        GPC and related privacy preference signals may apply only to the browser or device
        transmitting the signal; and specific categories of processing subject to applicable law.
        Certain processing activities may continue notwithstanding such signals where necessary to
        provide requested Services; required for security, fraud prevention, sanctions compliance, or
        legal obligations; necessary for strictly necessary or essential operational functions; or
        otherwise permitted under applicable law.
      </p>
      <p>
        DAWN and Andrena do not guarantee that third-party services, blockchain systems, wallet
        providers, analytics providers, or external platforms recognize or honor GPC or similar
        browser-based privacy signals.
      </p>
      <h4>10.5 Compliance and Blockchain Monitoring</h4>
      <p>
        We may use third-party compliance, analytics, blockchain monitoring, sanctions-screening,
        fraud-detection, or wallet-risk assessment providers to help prevent fraud or abuse; enforce
        geographic restrictions; comply with sanctions and legal obligations; and monitor the
        integrity of the Services.
      </p>
      <h4>10.6 Do Not Track Signals</h4>
      <p>
        Certain browsers may transmit “Do Not Track” (“<strong>DNT</strong>”) signals. Because there
        is no universally accepted standard for DNT signals, DAWN and Andrena do not currently respond
        to DNT browser signals except as otherwise required by applicable law.
      </p>

      <h3>
        <strong>11. Data Security</strong>
      </h3>
      <h4>11.1 Security Incidents</h4>
      <p>
        In the event of a suspected or confirmed security incident involving personal data, DAWN and
        Andrena may investigate, contain, remediate, cooperate with authorities, notify affected
        parties, and take other actions consistent with applicable law, operational requirements,
        legal obligations, and security practices.
      </p>
      <p>
        Nothing in this Privacy Policy constitutes a guarantee against security incidents,
        cyberattacks, unauthorized access, or third-party compromises.
      </p>
      <h4>11.2 Security Safeguards</h4>
      <p>
        DAWN and Andrena implement commercially reasonable administrative, technical, organizational,
        and physical safeguards designed to protect personal data against unauthorized access,
        disclosure, alteration, misuse, destruction, or loss. Such safeguards may include: encryption;
        access controls; authentication measures; network monitoring; security testing; logging and
        auditing; incident response procedures; vendor and infrastructure security reviews; and
        role-based access restrictions. Access to personal data is limited to personnel, contractors,
        service providers, and affiliated entities that reasonably require such access for
        operational, legal, security, compliance, or support purposes. Despite these measures, no
        system, network, blockchain, wallet integration, smart contract system, cloud environment,
        communication channel, or data transmission method can be guaranteed to be completely secure
        or error-free.
      </p>
      <p>
        Certain Services may involve interactions with public blockchain networks; smart contracts;
        digital wallets; decentralized infrastructure; third-party protocol systems; wallet providers;
        blockchain bridges; validators; oracles; analytics providers; and other third-party
        infrastructure outside DAWN’s or Andrena’s control. Such systems may involve additional risks,
        including smart contract vulnerabilities; exploits; blockchain forks; wallet compromise;
        validator failures; bridge failures; irreversible transactions; protocol attacks; data
        corruption; unauthorized third-party access; operational outages; and loss of digital assets
        or protocol positions.
      </p>
      <p>
        DAWN and Andrena are not responsible for the security, availability, integrity, or operation
        of third-party blockchain systems, wallet providers, smart contracts, or decentralized
        infrastructure not directly controlled by DAWN or Andrena.
      </p>
      <p>
        Users are solely responsible for maintaining the security of their wallets, devices,
        credentials, and accounts; safeguarding private keys and authentication credentials; verifying
        transaction details; and assessing the security of any third-party systems or services they
        choose to use. In the event of a security incident affecting personal data, DAWN and Andrena
        may investigate, mitigate, notify affected parties, and cooperate with authorities as required
        by applicable law.
      </p>

      <h3>
        <strong>12. Your Privacy Rights</strong>
      </h3>
      <h4>12.1 Privacy Rights</h4>
      <p>
        Depending on your jurisdiction and applicable law, you may have certain rights regarding your
        personal data, including the right to:
      </p>
      <ul role='list'>
        <li>request access to personal data we maintain about you;</li>
        <li>request correction of inaccurate or incomplete data;</li>
        <li>request deletion of certain personal data;</li>
        <li>request restriction of certain processing activities;</li>
        <li>object to certain categories of processing;</li>
        <li>withdraw consent where processing is based on consent;</li>
        <li>request portability of eligible personal data;</li>
        <li>opt out of certain categories of data sharing or targeted advertising; and</li>
        <li>lodge complaints with applicable regulatory authorities.</li>
      </ul>
      <p>
        These rights may be subject to legal limitations, verification procedures, fraud prevention
        requirements, security considerations, technical feasibility, operational requirements, and
        applicable legal exemptions.
      </p>
      <h4>12.2 Blockchain and Decentralized System Limitations</h4>
      <p>
        Certain requests may not apply to publicly accessible blockchain data, immutable blockchain
        records, smart contract interactions, wallet addresses, blockchain transaction records,
        decentralized storage systems, validator activity, protocol interaction data, security logs,
        compliance-related information, fraud prevention systems, or information retained for legal,
        regulatory, contractual, operational, telecommunications, infrastructure servicing, sanctions,
        cybersecurity, audit, or security purposes.
      </p>
      <p>
        Due to the decentralized, distributed, and immutable nature of blockchain systems, certain
        information recorded on public blockchains cannot be modified, deleted, anonymized, restricted,
        or controlled by DAWN or Andrena once published to the blockchain.
      </p>
      <p>
        This may include wallet addresses, transaction records, smart contract interactions, protocol
        activity, validator activity, timestamps, metadata, and other blockchain-related information
        that may remain permanently publicly accessible and independently indexed by third parties.
      </p>
      <p>
        DAWN and Andrena do not guarantee the deletion, removal, anonymization, or restriction of
        information that has been published to public blockchain systems, has been independently
        retained by third parties, has been stored in decentralized systems, or must be retained for
        legal, security, compliance, audit, fraud prevention, operational, telecommunications,
        infrastructure servicing, or regulatory purposes.
      </p>
      <h4>12.3 Submitting Privacy Rights Requests</h4>
      <p>
        Users may submit privacy rights requests by contacting:{' '}
        <a href='mailto:support@dawninternet.com'>support@dawninternet.com</a> or{' '}
        <a href='mailto:support@andrena.com'>support@andrena.com</a>
      </p>
      <p>
        Requests should specify the nature of the request, sufficient information to verify identity,
        and details necessary to process the request.
      </p>
      <p>
        DAWN and Andrena may require verification of identity or authority before processing requests.
        Authorized agents may be required to provide proof of authorization where required by
        applicable law.
      </p>
      <p>
        DAWN and Andrena may deny, limit, or condition requests where permitted by applicable law,
        including where identity cannot reasonably be verified, requests are excessive, repetitive, or
        abusive, compliance would impair legal, operational, security, fraud prevention,
        infrastructure servicing, telecommunications, or compliance functions, or information must be
        retained pursuant to legal, regulatory, contractual, accounting, sanctions, cybersecurity,
        dispute resolution, audit, or operational obligations.
      </p>
      <p>
        DAWN and Andrena may retain records of requests and related communications for compliance,
        legal, audit, fraud prevention, security, dispute resolution, and operational purposes.
      </p>
      <h4>12.4 Automated Processing and Compliance Screening</h4>
      <p>
        DAWN and Andrena may use automated systems, analytics tools, sanctions-screening systems,
        fraud-detection systems, wallet-screening technologies, geolocation systems, and compliance
        tools in connection with eligibility determinations, access restrictions, fraud prevention,
        sanctions compliance, abuse prevention, infrastructure protection, security monitoring, and
        operational risk management.
      </p>
      <p>
        Such systems may contribute to automated decisions relating to access restrictions, feature
        availability, compliance determinations, fraud prevention measures, or risk assessments,
        subject to applicable law.
      </p>

      <h3>
        <strong>13. California Privacy Rights</strong>
      </h3>
      <p>
        California residents may have rights under the California Consumer Privacy Act (“
        <strong>CCPA</strong>”), as amended by the California Privacy Rights Act (“
        <strong>CPRA</strong>”), including rights to:
      </p>
      <ul role='list'>
        <li>know the categories of personal information collected;</li>
        <li>know the categories of sources from which personal information is collected;</li>
        <li>understand the business or commercial purposes for processing;</li>
        <li>know the categories of third parties with whom information is shared;</li>
        <li>request deletion of certain personal information;</li>
        <li>request correction of inaccurate personal information;</li>
        <li>limit certain uses of sensitive personal information where applicable; and</li>
        <li>
          receive equal service and pricing without unlawful discrimination for exercising privacy
          rights.
        </li>
      </ul>
      <p>
        DAWN and Andrena do not currently sell personal information for monetary consideration.
        Certain processing activities involving analytics, advertising technologies, blockchain
        analytics, compliance providers, wallet-screening systems, or infrastructure monitoring
        providers may constitute “sharing” under California law depending on applicable legal
        interpretations.
      </p>
      <p>
        California residents may exercise applicable rights by contacting:{' '}
        <a href='mailto:support@dawninternet.com'>support@dawninternet.com</a>
      </p>
      <p>
        We may require verification of identity prior to processing requests. Certain rights and
        requests may not apply where information is retained for legal, security, fraud prevention,
        compliance, or operational purposes; is publicly available through blockchain systems; is
        deidentified or aggregated; or is otherwise exempt under applicable law.
      </p>
      <p>
        DAWN and Andrena are not responsible for the privacy, security, or data handling practices of
        third-party websites; wallet providers; blockchain protocols; smart contract systems;
        analytics providers; compliance providers; decentralized applications; or other third-party
        services not controlled by DAWN or Andrena.
      </p>

      <h3>
        <strong>14. Children’s Privacy</strong>
      </h3>
      <p>
        The Services are not directed to individuals under the age of eighteen (18), and DAWN and
        Andrena do not knowingly collect personal information from children.
      </p>
      <p>
        If DAWN or Andrena becomes aware that personal information has been collected from an
        individual under the applicable age of consent without appropriate authorization, reasonable
        steps may be taken to delete such information.
      </p>
      <p>
        Parents or guardians who believe that a child has provided personal information may contact{' '}
        <a href='mailto:support@dawninternet.com'>support@dawninternet.com</a> or{' '}
        <a href='mailto:support@andrena.com'>support@andrena.com</a>
      </p>

      <h3>
        <strong>15. Third-Party Links</strong>
      </h3>
      <p>
        The Services may contain links to, integrations with, or references to third-party websites,
        applications, wallet providers, blockchain networks, smart contract systems, analytics
        providers, decentralized protocols, infrastructure providers, social media platforms, APIs, or
        other third-party services.
      </p>
      <p>
        DAWN and Andrena do not control and are not responsible for the privacy practices; security
        practices; availability; content; data handling; operational integrity; or terms and policies
        of any third-party services or systems.
      </p>
      <p>
        Interactions with third-party services are governed solely by the applicable third party’s
        terms, privacy policies, and operational practices.
      </p>
      <p>
        Users access and interact with third-party services entirely at their own risk. DAWN and
        Andrena encourage users to review the privacy policies and terms of all third-party services
        before interacting with them.
      </p>

      <h3>
        <strong>16. Changes</strong>
      </h3>
      <p>
        DAWN and Andrena may update or modify this Privacy Policy from time to time for operational,
        legal, regulatory, security, technical, or business reasons.
      </p>
      <p>
        Updated versions will be posted with a revised effective date. Where required by applicable
        law, DAWN and Andrena may provide additional notice regarding material changes.
      </p>
      <p>
        Continued access to or use of the Services following publication of updated terms constitutes
        acknowledgment of the revised Privacy Policy to the extent permitted by law.
      </p>

      <h3>
        <strong>17. Privacy and Contacts</strong>
      </h3>
      <h4>17.1 Contacts</h4>
      <p>
        Questions, concerns, privacy requests, regulatory inquiries, or complaints regarding this
        Privacy Policy or personal data practices may be directed to:{' '}
        <a href='mailto:support@andrena.com'>support@andrena.com</a> or{' '}
        <a href='mailto:hello@dawninternet.com'>hello@dawninternet.com</a>
      </p>
      <p>
        DAWN and Andrena may request additional information to verify identity, authority, or request
        scope before responding to inquiries or exercising applicable rights. Communications
        transmitted via email or the internet may not be completely secure. Users should avoid
        transmitting sensitive information, private keys, seed phrases, or highly confidential
        information through unsecured communication channels.
      </p>
      <h4>17.2 EU and UK Privacy Representatives</h4>
      <p>
        Where required by applicable law, DAWN or Andrena may designate an EU GDPR representative, UK
        GDPR representative, or other local privacy representative. Representative information will be
        made available where legally required.
      </p>

      <h3>
        <strong>18. Relationship to Terms</strong>
      </h3>
      <p>
        This Privacy Policy is incorporated into and forms part of the DAWN Terms of Use; Rewards
        Program Terms; InfraFi Terms of Use and Risk Disclosure; Andrena Commercial Terms; and any
        supplemental agreements, clickwrap terms, onboarding flows, investor materials, or
        interface-specific agreements governing particular Services, applications, dashboards, protocol
        features, infrastructure systems, or interactions. In the event of a conflict between this
        Privacy Policy and any separate written agreement governing specific Services, the applicable
        separate agreement may control to the extent of such conflict.
      </p>
    </LegalPage>
  )
}

export default PrivacyPolicyPage
