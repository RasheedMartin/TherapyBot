import { Link, List, ListItem, ListItemText, Paper, Typography } from "@mui/material";

const external = { target: "_blank", rel: "noopener noreferrer" } as const;

/** Other routes into care that the directory search can't cover (availability, cost, insurance). */
export const CareResources = ({ zip }: { zip: string }) => (
  <Paper variant="outlined" sx={{ p: 2.5, borderRadius: 3 }}>
    <Typography variant="subtitle1" fontWeight={600} gutterBottom>
      More ways to find care
    </Typography>
    <List dense disablePadding>
      <ListItem disableGutters>
        <ListItemText
          primary={
            <Link href={`https://www.psychologytoday.com/us/therapists/${zip || ""}`} {...external}>
              Therapist directory with availability & insurance filters
            </Link>
          }
          secondary="Psychology Today lets you filter by insurance, specialty, and who's accepting clients."
        />
      </ListItem>
      <ListItem disableGutters>
        <ListItemText
          primary="Call the number on your insurance card"
          secondary="Ask member services for in-network mental health providers near you."
        />
      </ListItem>
      <ListItem disableGutters>
        <ListItemText
          primary={
            <Link href="https://openpathcollective.org" {...external}>
              Open Path Collective
            </Link>
          }
          secondary="Lower-cost sessions for people without adequate insurance."
        />
      </ListItem>
      <ListItem disableGutters>
        <ListItemText
          primary={
            <Link href="https://findahealthcenter.hrsa.gov" {...external}>
              Community health centers
            </Link>
          }
          secondary="Federally funded clinics with sliding-scale fees based on income."
        />
      </ListItem>
      <ListItem disableGutters>
        <ListItemText
          primary={<Link href="tel:18006624357">SAMHSA National Helpline: 1-800-662-4357</Link>}
          secondary="Free, confidential treatment referrals, 24/7."
        />
      </ListItem>
      <ListItem disableGutters>
        <ListItemText
          primary={<Link href="tel:988">In crisis? Call or text 988</Link>}
          secondary="Suicide & Crisis Lifeline, available 24/7."
        />
      </ListItem>
    </List>
  </Paper>
);
