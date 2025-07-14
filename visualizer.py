import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import os
from pathlib import Path

class TrendVisualizer:
    def __init__(self, config=None, output_dir: str = "visualizations"):
        self.logger = logging.getLogger(__name__)
        self.config = config
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        # Default styling
        self.color_scheme = {
            'primary': '#1f77b4',
            'secondary': '#ff7f0e',
            'success': '#2ca02c',
            'warning': '#d62728',
            'info': '#9467bd',
            'twitter': '#1DA1F2',
            'github': '#333333',
            'reddit': '#FF4500',
            'hackernews': '#FF6600'
        }
        
        self.source_colors = {
            'twitter': self.color_scheme['twitter'],
            'github': self.color_scheme['github'],
            'reddit': self.color_scheme['reddit'],
            'hackernews': self.color_scheme['hackernews']
        }
    
    def create_sentiment_timeline(self, analysis_data: List[Dict], 
                                 output_file: str = None) -> str:
        """Create a sentiment timeline visualization."""
        try:
            if not analysis_data:
                self.logger.warning("No analysis data provided for sentiment timeline")
                return None
            
            # Prepare data
            df_data = []
            for analysis in analysis_data:
                timestamp = analysis.get('timestamp')
                if timestamp:
                    try:
                        # Handle different timestamp formats
                        if isinstance(timestamp, str):
                            dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                        else:
                            dt = timestamp
                        
                        df_data.append({
                            'timestamp': dt,
                            'sentiment': analysis.get('sentiment_score', 0),
                            'trends_count': analysis.get('total_trends', 0)
                        })
                    except Exception as e:
                        self.logger.warning(f"Invalid timestamp format: {timestamp}, {e}")
                        continue
            
            if not df_data:
                self.logger.warning("No valid data for sentiment timeline")
                return None
            
            df = pd.DataFrame(df_data)
            df = df.sort_values('timestamp')
            
            # Create the plot
            fig = go.Figure()
            
            # Add sentiment line
            fig.add_trace(go.Scatter(
                x=df['timestamp'],
                y=df['sentiment'],
                mode='lines+markers',
                name='Sentiment Score',
                line=dict(color=self.color_scheme['primary'], width=3),
                marker=dict(size=8),
                hovertemplate='<b>%{x}</b><br>Sentiment: %{y:.3f}<extra></extra>'
            ))
            
            # Add horizontal reference lines
            fig.add_hline(y=0, line_dash="dash", line_color="gray", 
                         annotation_text="Neutral", annotation_position="right")
            fig.add_hline(y=0.2, line_dash="dot", line_color="green", opacity=0.5,
                         annotation_text="Positive", annotation_position="right")
            fig.add_hline(y=-0.2, line_dash="dot", line_color="red", opacity=0.5,
                         annotation_text="Negative", annotation_position="right")
            
            # Update layout
            fig.update_layout(
                title={
                    'text': 'Tech Trends Sentiment Over Time',
                    'x': 0.5,
                    'xanchor': 'center',
                    'font': {'size': 20}
                },
                xaxis_title='Time',
                yaxis_title='Sentiment Score',
                yaxis=dict(range=[-1, 1]),
                hovermode='x unified',
                template='plotly_white',
                width=1000,
                height=500,
                showlegend=False
            )
            
            # Save the plot
            if not output_file:
                output_file = f"sentiment_timeline_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
            
            output_path = self.output_dir / output_file
            fig.write_html(str(output_path))
            
            self.logger.info(f"Sentiment timeline saved to {output_path}")
            return str(output_path)
            
        except Exception as e:
            self.logger.error(f"Error creating sentiment timeline: {e}")
            return None
    
    def create_source_breakdown_chart(self, trends_data: List[Dict],
                                    output_file: str = None) -> str:
        """Create a source breakdown pie chart."""
        try:
            if not trends_data:
                self.logger.warning("No trends data provided for source breakdown")
                return None
            
            # Count trends by source
            source_counts = {}
            source_engagement = {}
            
            for trend in trends_data:
                source = trend.get('source', 'unknown')
                engagement = trend.get('engagement_score', 0)
                
                source_counts[source] = source_counts.get(source, 0) + 1
                source_engagement[source] = source_engagement.get(source, 0) + engagement
            
            if not source_counts:
                self.logger.warning("No valid source data found")
                return None
            
            # Create subplots
            from plotly.subplots import make_subplots
            
            fig = make_subplots(
                rows=1, cols=2,
                subplot_titles=('Trends Count by Source', 'Total Engagement by Source'),
                specs=[[{"type": "pie"}, {"type": "pie"}]]
            )
            
            # Colors for sources
            colors = [self.source_colors.get(source, self.color_scheme['primary']) 
                     for source in source_counts.keys()]
            
            # Count pie chart
            fig.add_trace(go.Pie(
                labels=list(source_counts.keys()),
                values=list(source_counts.values()),
                name="Count",
                marker_colors=colors,
                textinfo='label+percent',
                hovertemplate='<b>%{label}</b><br>Count: %{value}<br>Percentage: %{percent}<extra></extra>'
            ), 1, 1)
            
            # Engagement pie chart
            fig.add_trace(go.Pie(
                labels=list(source_engagement.keys()),
                values=list(source_engagement.values()),
                name="Engagement",
                marker_colors=colors,
                textinfo='label+percent',
                hovertemplate='<b>%{label}</b><br>Engagement: %{value:.0f}<br>Percentage: %{percent}<extra></extra>'
            ), 1, 2)
            
            # Update layout
            fig.update_layout(
                title={
                    'text': 'Trends Analysis by Source',
                    'x': 0.5,
                    'xanchor': 'center',
                    'font': {'size': 20}
                },
                template='plotly_white',
                width=1200,
                height=500,
                showlegend=False
            )
            
            # Save the plot
            if not output_file:
                output_file = f"source_breakdown_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
            
            output_path = self.output_dir / output_file
            fig.write_html(str(output_path))
            
            self.logger.info(f"Source breakdown chart saved to {output_path}")
            return str(output_path)
            
        except Exception as e:
            self.logger.error(f"Error creating source breakdown chart: {e}")
            return None
    
    def create_engagement_scatter(self, trends_data: List[Dict],
                                output_file: str = None) -> str:
        """Create engagement vs sentiment scatter plot."""
        try:
            if not trends_data:
                self.logger.warning("No trends data provided for engagement scatter")
                return None
            
            # Prepare data with sentiment calculation (simplified)
            df_data = []
            for trend in trends_data:
                content = f"{trend.get('topic', '')} {trend.get('content', '')}"
                # Simplified sentiment based on keywords (replace with actual sentiment analysis if needed)
                positive_words = ['good', 'great', 'amazing', 'excellent', 'breakthrough', 'innovation']
                negative_words = ['bad', 'terrible', 'awful', 'problem', 'issue', 'bug', 'error']
                
                content_lower = content.lower()
                pos_count = sum(1 for word in positive_words if word in content_lower)
                neg_count = sum(1 for word in negative_words if word in content_lower)
                
                # Simple sentiment calculation
                if pos_count > neg_count:
                    sentiment = 0.3
                elif neg_count > pos_count:
                    sentiment = -0.3
                else:
                    sentiment = 0.0
                
                df_data.append({
                    'engagement': trend.get('engagement_score', 0),
                    'sentiment': sentiment,
                    'source': trend.get('source', 'unknown'),
                    'topic': trend.get('topic', 'Unknown')[:50] + '...' if len(trend.get('topic', '')) > 50 else trend.get('topic', 'Unknown')
                })
            
            if not df_data:
                self.logger.warning("No valid data for engagement scatter")
                return None
            
            df = pd.DataFrame(df_data)
            
            # Create scatter plot
            fig = px.scatter(
                df,
                x='engagement',
                y='sentiment',
                color='source',
                hover_data=['topic'],
                color_discrete_map=self.source_colors,
                title='Engagement vs Sentiment by Source'
            )
            
            # Update traces for better hover
            fig.update_traces(
                hovertemplate='<b>%{customdata[0]}</b><br>' +
                             'Engagement: %{x}<br>' +
                             'Sentiment: %{y:.2f}<br>' +
                             'Source: %{fullData.name}<extra></extra>'
            )
            
            # Update layout
            fig.update_layout(
                xaxis_title='Engagement Score',
                yaxis_title='Sentiment Score',
                template='plotly_white',
                width=1000,
                height=600,
                hovermode='closest'
            )
            
            # Save the plot
            if not output_file:
                output_file = f"engagement_scatter_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
            
            output_path = self.output_dir / output_file
            fig.write_html(str(output_path))
            
            self.logger.info(f"Engagement scatter plot saved to {output_path}")
            return str(output_path)
            
        except Exception as e:
            self.logger.error(f"Error creating engagement scatter: {e}")
            return None
    
    def create_top_topics_bar(self, trends_data: List[Dict], top_n: int = 15,
                            output_file: str = None) -> str:
        """Create a bar chart of top topics by engagement."""
        try:
            if not trends_data:
                self.logger.warning("No trends data provided for top topics bar chart")
                return None
            
            # Sort by engagement and get top N
            sorted_trends = sorted(trends_data, 
                                 key=lambda x: x.get('engagement_score', 0), 
                                 reverse=True)[:top_n]
            
            if not sorted_trends:
                self.logger.warning("No valid trends for top topics")
                return None
            
            # Prepare data
            topics = []
            engagements = []
            sources = []
            
            for trend in sorted_trends:
                topic = trend.get('topic', 'Unknown')
                # Truncate long topic names
                if len(topic) > 30:
                    topic = topic[:27] + '...'
                
                topics.append(topic)
                engagements.append(trend.get('engagement_score', 0))
                sources.append(trend.get('source', 'unknown'))
            
            # Create bar chart
            fig = go.Figure()
            
            # Add bars with colors by source
            for source in set(sources):
                source_topics = []
                source_engagements = []
                for i, s in enumerate(sources):
                    if s == source:
                        source_topics.append(topics[i])
                        source_engagements.append(engagements[i])
                
                if source_topics:
                    fig.add_trace(go.Bar(
                        x=source_engagements,
                        y=source_topics,
                        name=source.title(),
                        orientation='h',
                        marker_color=self.source_colors.get(source, self.color_scheme['primary']),
                        hovertemplate='<b>%{y}</b><br>Engagement: %{x}<br>Source: ' + source + '<extra></extra>'
                    ))
            
            # Update layout
            fig.update_layout(
                title={
                    'text': f'Top {top_n} Topics by Engagement Score',
                    'x': 0.5,
                    'xanchor': 'center',
                    'font': {'size': 20}
                },
                xaxis_title='Engagement Score',
                yaxis_title='Topics',
                template='plotly_white',
                width=1000,
                height=max(600, top_n * 30),  # Dynamic height based on number of topics
                showlegend=True,
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            )
            
            # Save the plot
            if not output_file:
                output_file = f"top_topics_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
            
            output_path = self.output_dir / output_file
            fig.write_html(str(output_path))
            
            self.logger.info(f"Top topics bar chart saved to {output_path}")
            return str(output_path)
            
        except Exception as e:
            self.logger.error(f"Error creating top topics bar chart: {e}")
            return None
    
    def create_comprehensive_dashboard(self, analysis_data: List[Dict], 
                                     trends_data: List[Dict],
                                     output_file: str = None) -> str:
        """Create a comprehensive dashboard with multiple visualizations."""
        try:
            if not trends_data:
                self.logger.warning("No data provided for comprehensive dashboard")
                return None
            
            from plotly.subplots import make_subplots
            
            # Create subplots
            fig = make_subplots(
                rows=3, cols=2,
                subplot_titles=(
                    'Sentiment Over Time', 'Source Distribution',
                    'Top Topics by Engagement', 'Engagement vs Time',
                    'Source Engagement Comparison', 'Daily Trends Count'
                ),
                specs=[
                    [{"type": "scatter"}, {"type": "pie"}],
                    [{"type": "bar", "colspan": 2}, None],
                    [{"type": "bar"}, {"type": "bar"}]
                ],
                vertical_spacing=0.1,
                horizontal_spacing=0.1
            )
            
            # 1. Sentiment timeline (if analysis data available)
            if analysis_data:
                sentiment_df = []
                for analysis in analysis_data:
                    timestamp = analysis.get('timestamp')
                    if timestamp:
                        try:
                            if isinstance(timestamp, str):
                                dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                            else:
                                dt = timestamp
                            sentiment_df.append({
                                'timestamp': dt,
                                'sentiment': analysis.get('sentiment_score', 0)
                            })
                        except:
                            continue
                
                if sentiment_df:
                    sentiment_df = pd.DataFrame(sentiment_df).sort_values('timestamp')
                    fig.add_trace(go.Scatter(
                        x=sentiment_df['timestamp'],
                        y=sentiment_df['sentiment'],
                        mode='lines+markers',
                        name='Sentiment',
                        line=dict(color=self.color_scheme['primary'])
                    ), 1, 1)
            
            # 2. Source distribution
            source_counts = {}
            for trend in trends_data:
                source = trend.get('source', 'unknown')
                source_counts[source] = source_counts.get(source, 0) + 1
            
            if source_counts:
                colors = [self.source_colors.get(source, self.color_scheme['primary']) 
                         for source in source_counts.keys()]
                fig.add_trace(go.Pie(
                    labels=list(source_counts.keys()),
                    values=list(source_counts.values()),
                    marker_colors=colors,
                    name="Sources"
                ), 1, 2)
            
            # 3. Top topics
            top_trends = sorted(trends_data, 
                              key=lambda x: x.get('engagement_score', 0), 
                              reverse=True)[:10]
            
            if top_trends:
                topics = [trend.get('topic', 'Unknown')[:25] + '...' 
                         if len(trend.get('topic', '')) > 25 
                         else trend.get('topic', 'Unknown') for trend in top_trends]
                engagements = [trend.get('engagement_score', 0) for trend in top_trends]
                
                fig.add_trace(go.Bar(
                    x=engagements,
                    y=topics,
                    orientation='h',
                    marker_color=self.color_scheme['secondary'],
                    name="Top Topics"
                ), 2, 1)
            
            # 4. Engagement by source
            source_engagement = {}
            for trend in trends_data:
                source = trend.get('source', 'unknown')
                source_engagement[source] = source_engagement.get(source, 0) + trend.get('engagement_score', 0)
            
            if source_engagement:
                fig.add_trace(go.Bar(
                    x=list(source_engagement.keys()),
                    y=list(source_engagement.values()),
                    marker_color=[self.source_colors.get(source, self.color_scheme['primary']) 
                                for source in source_engagement.keys()],
                    name="Source Engagement"
                ), 3, 1)
            
            # 5. Trends count by hour (if timestamps available)
            hourly_counts = {}
            for trend in trends_data:
                # Use current time if no timestamp in trend data
                hour = datetime.now().hour
                hourly_counts[hour] = hourly_counts.get(hour, 0) + 1
            
            if hourly_counts:
                fig.add_trace(go.Bar(
                    x=list(hourly_counts.keys()),
                    y=list(hourly_counts.values()),
                    marker_color=self.color_scheme['info'],
                    name="Hourly Trends"
                ), 3, 2)
            
            # Update layout
            fig.update_layout(
                title={
                    'text': 'Tech Trends Comprehensive Dashboard',
                    'x': 0.5,
                    'xanchor': 'center',
                    'font': {'size': 24}
                },
                template='plotly_white',
                width=1400,
                height=1200,
                showlegend=False
            )
            
            # Save the dashboard
            if not output_file:
                output_file = f"dashboard_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
            
            output_path = self.output_dir / output_file
            fig.write_html(str(output_path))
            
            self.logger.info(f"Comprehensive dashboard saved to {output_path}")
            return str(output_path)
            
        except Exception as e:
            self.logger.error(f"Error creating comprehensive dashboard: {e}")
            return None
    
    def cleanup_old_visualizations(self, days: int = 7):
        """Clean up visualization files older than specified days."""
        try:
            cutoff_time = datetime.now() - timedelta(days=days)
            
            for file_path in self.output_dir.glob("*.html"):
                if file_path.stat().st_mtime < cutoff_time.timestamp():
                    file_path.unlink()
                    self.logger.info(f"Deleted old visualization: {file_path}")
            
        except Exception as e:
            self.logger.error(f"Error cleaning up visualizations: {e}")
    
    def get_visualization_summary(self) -> Dict[str, Any]:
        """Get summary of available visualizations."""
        try:
            visualizations = list(self.output_dir.glob("*.html"))
            
            summary = {
                'total_files': len(visualizations),
                'output_directory': str(self.output_dir),
                'recent_files': []
            }
            
            # Get recent files (last 5)
            recent_files = sorted(visualizations, 
                                key=lambda x: x.stat().st_mtime, 
                                reverse=True)[:5]
            
            for file_path in recent_files:
                summary['recent_files'].append({
                    'name': file_path.name,
                    'path': str(file_path),
                    'created': datetime.fromtimestamp(file_path.stat().st_mtime).isoformat(),
                    'size_kb': round(file_path.stat().st_size / 1024, 2)
                })
            
            return summary
            
        except Exception as e:
            self.logger.error(f"Error getting visualization summary: {e}")
            return {'error': str(e)}