import { Composition, Still, staticFile } from 'remotion'
import { COUNTDOWN, Guide, Video, type Data } from './Video'
import { Thumbnail } from './Thumbnail'

const load = async () => (await fetch(staticFile('data.json'))).json() as Promise<Data>
const none = { data: null as unknown as Data }

export const Root = () => (
  <>
    <Composition id="SpecCheck" component={Video} width={1920} height={1080} fps={60} durationInFrames={600} defaultProps={none}
      calculateMetadata={async () => { const data = await load(); return { durationInFrames: data.frames, props: { data } } }} />
    <Composition id="Silent" component={Video} width={1920} height={1080} fps={60} durationInFrames={600} defaultProps={{ ...none, silent: true }}
      calculateMetadata={async () => { const data = await load(); return { durationInFrames: data.frames, props: { data, silent: true } } }} />
    <Composition id="Guide" component={Guide} width={1920} height={1080} fps={60} durationInFrames={600} defaultProps={none}
      calculateMetadata={async () => { const data = await load(); return { durationInFrames: COUNTDOWN + data.frames, props: { data } } }} />
    <Still id="Thumbnail" component={Thumbnail} width={1280} height={720} defaultProps={none}
      calculateMetadata={async () => ({ props: { data: await load() } })} />
  </>
)
