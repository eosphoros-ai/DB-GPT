"use client"
import ChatBoxComp from '@/components/chatBox';
import { Chart, LineAdvance, Interval, Tooltip, getTheme } from 'bizcharts';
import { Card, CardContent, Typography, Grid, styled, Sheet } from '@/lib/mui';
import { Stack } from '@mui/material';
import useAgentChat from '@/hooks/useAgentChat';


const Item = styled(Sheet)(({ theme }) => ({
  ...theme.typography.body2,
  padding: theme.spacing(1),
  textAlign: 'center',
  borderRadius: 4,
  color: theme.vars.palette.text.secondary,
}));

const Agents = () => {
  const { handleChatSubmit, history } = useAgentChat({
    queryAgentURL: `/v1/chat/completions`,
  });

  const data = [
    {
      month: "Jan",
      city: "Tokyo",
      temperature: 7
    },
    {
      month: "Feb",
      city: "Tokyo",
      temperature: 13
    },
    {
      month: "Mar",
      city: "Tokyo",
      temperature: 16.5
    },
    {
      month: "Apr",
      city: "Tokyo",
      temperature: 14.5
    },
    {
      month: "May",
      city: "Tokyo",
      temperature: 10
    },
    {
      month: "Jun",
      city: "Tokyo",
      temperature: 7.5
    },
    {
      month: "Jul",
      city: "Tokyo",
      temperature: 9.2
    },
    {
      month: "Aug",
      city: "Tokyo",
      temperature: 14.5
    },
    {
      month: "Sep",
      city: "Tokyo",
      temperature: 9.3
    },
    {
      month: "Oct",
      city: "Tokyo",
      temperature: 8.3
    },
    {
      month: "Nov",
      city: "Tokyo",
      temperature: 8.9
    },
    {
      month: "Dec",
      city: "Tokyo",
      temperature: 5.6
    },
  ];

  const d1 = [
    { year: '1951 年', sales: 0 },
    { year: '1952 年', sales: 52 },
    { year: '1956 年', sales: 61 },
    { year: '1957 年', sales: 45 },
    { year: '1958 年', sales: 48 },
    { year: '1959 年', sales: 38 },
    { year: '1960 年', sales: 38 },
    { year: '1962 年', sales: 38 },
  ];

  const topCard = [{
    label: 'Revenue Won',
    value: '$7,811,851'
  }, {
    label: 'Close %',
    value: '37.7%'
  }, {
    label: 'AVG Days to Close',
    value: '121'
  }, {
    label: 'Opportunities Won',
    value: '526'
  }];

  return (
    <div className='p-4 flex flex-row gap-6 min-h-full w-full'>
      <div className='flex w-full'>
        <Grid container spacing={2} sx={{ flexGrow: 1 }}>
          <Grid xs={8}>
            <Stack spacing={2} className='h-full'>
              <Item>
                <Grid container spacing={2}>
                  {topCard.map((item) => (
                    <Grid key={item.label} xs={3}>
                      <Card  className="flex-1 h-full">
                        <CardContent className="justify-around">
                          <Typography gutterBottom component="div">
                            {item.label}
                          </Typography>
                          <Typography>
                            {item.value}
                          </Typography>
                        </CardContent>
                      </Card>
                    </Grid>
                  ))}
                </Grid>
              </Item>
              <Item className='flex-1'>
                <Card className='h-full'>
                  <CardContent className='h-full'>
                    <Typography gutterBottom component="div">
                      Revenue Won by Month
                    </Typography>
                    <div className='flex-1'>
                      <Chart padding={[10, 20, 50, 40]} autoFit data={data} >
                        <LineAdvance
                          shape="smooth"
                          point
                          area
                          position="month*temperature"
                          color="city"
                        />
                      </Chart>
                    </div>
                  </CardContent>
                </Card>
              </Item>
              <Item className='flex-1'>
                <Grid container spacing={2} className='h-full'>
                  <Grid xs={4} className='h-full'>
                    <Card className='flex-1 h-full'>
                      <CardContent className='h-full'>
                        <Typography gutterBottom component="div">
                          Close % by Month
                        </Typography>
                        <div className='flex-1'>
                          <Chart  autoFit data={d1} >
                            <Interval position="year*sales" style={{ lineWidth: 3, stroke: getTheme().colors10[0] }} />
                            <Tooltip shared />
                          </Chart>
                        </div>
                      </CardContent>
                    </Card>
                  </Grid>
                  <Grid xs={4} className='h-full'>
                    <Card className='flex-1 h-full'>
                      <CardContent className='h-full'>
                        <Typography gutterBottom component="div">
                          Close % by Month
                        </Typography>
                        <div className='flex-1'>
                          <Chart  autoFit data={d1} >
                            <Interval position="year*sales" style={{ lineWidth: 3, stroke: getTheme().colors10[0] }} />
                            <Tooltip shared />
                          </Chart>
                        </div>
                      </CardContent>
                    </Card>
                  </Grid>
                  <Grid xs={4} className='h-full'>
                    <Card className='flex-1 h-full'>
                      <CardContent className='h-full'>
                        <Typography gutterBottom component="div">
                          Close % by Month
                        </Typography>
                        <div className='flex-1'>
                          <Chart  autoFit data={d1} >
                            <Interval position="year*sales" style={{ lineWidth: 3, stroke: getTheme().colors10[0] }} />
                            <Tooltip shared />
                          </Chart>
                        </div>
                      </CardContent>
                    </Card>
                  </Grid>
                </Grid>
              </Item>
            </Stack>
          </Grid>
          <Grid xs={4}>
            <ChatBoxComp messages={history} onSubmit={handleChatSubmit}/>
          </Grid>
        </Grid>
      </div>
    </div>
  )
}

export default Agents;