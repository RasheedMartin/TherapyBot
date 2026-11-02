import { Box, FormControlLabel, Radio, RadioGroup, Stack, Typography } from "@mui/material";
import type { Instrument } from "../../api/types";

/** A screening's questions with its answer scale, for the therapist entering results or the client completing one. */
export const ScreeningQuestions = ({
  instrument,
  answers,
  onAnswer,
}: {
  instrument: Instrument;
  answers: Record<number, number>;
  onAnswer: (item: number, value: number) => void;
}) => (
  <>
    {instrument.prompt && <Typography color="text.secondary" mb={2}>{instrument.prompt}</Typography>}
    <Stack spacing={2}>
      {instrument.items.map((item, i) => (
        <Box key={i} component="fieldset" sx={{ border: 0, p: 0, m: 0 }}>
          <Typography component="legend" fontWeight={500}>{i + 1}. {item}</Typography>
          <RadioGroup row value={answers[i] ?? ""} onChange={(e) => onAnswer(i, Number(e.target.value))}>
            {instrument.options.map((o) => (
              <FormControlLabel key={o.value} value={o.value} control={<Radio size="small" />}
                                label={<Typography variant="body2">{o.label}</Typography>} />
            ))}
          </RadioGroup>
        </Box>
      ))}
    </Stack>
  </>
);
