import { Alert, Box, Container, Typography } from "@mui/material";

// DRAFT COPY: must be reviewed by a qualified attorney before public launch.
const LAST_UPDATED = "October 30, 2026";

const LegalPage = ({ title, children }: { title: string; children: React.ReactNode }) => (
  <Container maxWidth="md" sx={{ py: { xs: 4, md: 8 } }}>
    <Typography variant="h3" component="h1" gutterBottom>
      {title}
    </Typography>
    <Typography color="text.secondary" mb={3}>
      Last updated {LAST_UPDATED}
    </Typography>
    <Alert severity="info" sx={{ mb: 4 }}>
      This is a draft pending legal review.
    </Alert>
    <Box
      sx={{
        "& h2": { typography: "h6", mt: 4, mb: 1 },
        "& p, & li": { typography: "body1", color: "text.secondary" },
        "& ul": { pl: 3 },
      }}
    >
      {children}
    </Box>
  </Container>
);

export const TermsPage = () => (
  <LegalPage title="Terms of Use">
    <h2>What TherapyBot is</h2>
    <p>
      TherapyBot is an AI-powered wellness tool that offers emotional support, general information about evidence-based
      coping skills, and help finding professional care. It is not a therapist, does not provide medical or mental
      health diagnosis or treatment, and is not a substitute for care from a licensed professional.
    </p>
    <h2>Not for emergencies</h2>
    <p>
      TherapyBot is not monitored by people and cannot respond to emergencies. If you are in crisis or thinking about
      harming yourself or others, call or text 988 (US), call 911, or contact your local emergency services.
    </p>
    <h2>Who can use it</h2>
    <p>You must be at least 18 years old and able to agree to these terms.</p>
    <h2>Your responsibilities</h2>
    <ul>
      <li>Keep your login details secure.</li>
      <li>Use your own judgment. AI can make mistakes; don't rely on it for decisions about medication or treatment.</li>
      <li>Don't misuse the service, attempt to break it, or use it to harm others.</li>
    </ul>
    <h2>Your content</h2>
    <p>
      You own what you write. You give us permission to process it only to provide the service to you, as described in
      our Privacy Policy.
    </p>
    <h2>Changes and termination</h2>
    <p>
      We may update these terms and will tell you about significant changes. You can delete your account at any time
      from your profile.
    </p>
  </LegalPage>
);

export const PrivacyPage = () => (
  <LegalPage title="Privacy Policy">
    <h2>What we collect</h2>
    <ul>
      <li>Account details: username, email address, and a securely hashed password.</li>
      <li>Profile details you choose to add, such as a display name, goals, ZIP code, and insurance.</li>
      <li>Your conversations with TherapyBot, your plans and check-ins, and providers you save.</li>
      <li>Session notes you choose to add, and their explanations.</li>
      <li>Reminder preferences, including your time zone.</li>
      <li>The date you confirmed your age and accepted our terms.</li>
    </ul>
    <h2>How we use it</h2>
    <p>
      Only to provide and improve the service for you: generating replies, personalizing conversations, and helping you
      find care. We do not sell your data, use it for advertising, or share it with your employer, insurer, or anyone
      else without your explicit permission.
    </p>
    <h2>Service providers</h2>
    <p>
      To generate replies, plans, and explanations of session notes, the relevant text is sent to our AI provider
      (Groq). Location you share to sort providers by distance stays in your browser and is never sent to us. We also use providers for hosting, our
      database, and sending email. They may process your data only on our behalf.
    </p>
    <h2>Health information</h2>
    <p>
      What you share may include sensitive health information. We treat all conversations as sensitive, encrypt them in
      transit, and limit access. TherapyBot is a consumer wellness app and is not a HIPAA-covered healthcare provider.
    </p>
    <h2>Your choices and rights</h2>
    <ul>
      <li>Download all your data at any time from your profile.</li>
      <li>Delete your account and all conversations permanently from your profile.</li>
      <li>Edit or remove profile details whenever you like.</li>
      <li>Turn off reminder emails from your profile or with the link in any reminder.</li>
      <li>
        If you turn on calendar sync, anyone with your private calendar link can see your plan steps. You can reset or
        turn off the link at any time, and choose discreet titles.
      </li>
    </ul>
    <h2>Retention</h2>
    <p>
      We keep your data until you delete it or your account. Deleted data is removed from our systems, except where we
      are legally required to keep it.
    </p>
    <h2>Contact</h2>
    <p>Questions about privacy? Contact us at privacy@therapybot.app.</p>
  </LegalPage>
);
